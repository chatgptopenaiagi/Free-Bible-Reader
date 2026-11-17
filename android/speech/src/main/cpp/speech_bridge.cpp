// FREE BIBLE READER Android adapter. Piper/eSpeak upstream sources retain their licenses.
#include <jni.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include "piper.h"
#include "espeak-ng/speak_lib.h"
#include "native_synthesis_lock.h"

namespace {
std::atomic<uint64_t> generation{0};
// This adapter is the only consumer of the library in FBR. Also acquire the upstream
// process-global session mutex so future Kotlin consumers cannot race eSpeak state.
std::mutex bridgeMutex;
struct PiperDeleter { void operator()(piper_synthesizer* p) const { if(p) piper_free(p); } };
std::unique_ptr<piper_synthesizer,PiperDeleter> cached;
std::string cachedModel;

std::string str(JNIEnv* env, jstring input) {
  if(!input) return {};
  const char* p=env->GetStringUTFChars(input,nullptr);
  if(!p) throw std::runtime_error("UTF8_ALLOCATION_FAILED");
  std::string result(p);env->ReleaseStringUTFChars(input,p);return result;
}
std::string bytes(JNIEnv* env,jbyteArray input) {
  if(!input) return {};
  const jsize size=env->GetArrayLength(input);std::string result(size,'\0');
  env->GetByteArrayRegion(input,0,size,reinterpret_cast<jbyte*>(result.data()));return result;
}
void put16(std::ostream& out,uint16_t v){ char p[2]={char(v),char(v>>8)};out.write(p,2); }
void put32(std::ostream& out,uint32_t v){char p[4]={char(v),char(v>>8),char(v>>16),char(v>>24)};out.write(p,4);}
struct Wave {
  std::fstream out;uint64_t samples=0;int rate=22050;double squared=0;int peak=0;uint64_t token;uint64_t modelChunks=0,finalChunkSamples=0;
  Wave(const std::string& path,uint64_t t):out(path,std::ios::out|std::ios::binary|std::ios::trunc),token(t){
    if(!out)throw std::runtime_error("AUDIO_FILE_NOT_WRITABLE");for(int i=0;i<44;i++)out.put(0);
  }
  void append(const short* p,size_t n){
    if(generation.load()!=token)throw std::runtime_error("CANCELLED");
    if(samples+n>uint64_t(rate)*600)throw std::runtime_error("AUDIO_DURATION_LIMIT");
    for(size_t i=0;i<n;i++){put16(out,uint16_t(p[i]));const int s=p[i];peak=std::max(peak,std::abs(s));squared+=double(s)*s;}samples+=n;
    if(!out)throw std::runtime_error("AUDIO_WRITE_FAILED");
  }
  void append(const float* p,size_t n){
    short converted[4096];
    for(size_t offset=0;offset<n;offset+=4096){size_t count=std::min<size_t>(4096,n-offset);for(size_t i=0;i<count;i++)converted[i]=short(std::lrint(std::clamp(p[offset+i],-1.0f,1.0f)*32767));append(converted,count);}
  }
  std::string finish(){
    if(samples==0||peak==0)throw std::runtime_error("EMPTY_AUDIO");
    const uint32_t size=uint32_t(samples*2);out.seekp(0);out.write("RIFF",4);put32(out,size+36);out.write("WAVEfmt ",8);put32(out,16);put16(out,1);put16(out,1);put32(out,rate);put32(out,rate*2);put16(out,2);put16(out,16);out.write("data",4);put32(out,size);out.flush();
    if(!out)throw std::runtime_error("AUDIO_WRITE_FAILED");
    std::ostringstream json;json<<"{\"sample_rate\":"<<rate<<",\"samples\":"<<samples<<",\"channels\":1,\"sample_width\":2,\"duration_seconds\":"<<std::setprecision(12)<<double(samples)/rate<<",\"peak\":"<<peak<<",\"rms\":"<<std::sqrt(squared/samples)<<",\"model_chunks\":"<<modelChunks<<",\"final_chunk_samples\":"<<finalChunkSamples<<"}";return json.str();
  }
};
thread_local Wave* currentWave=nullptr;
thread_local bool callbackError=false;
int espeakCallback(short* samples,int count,espeak_EVENT*){
  if(!currentWave)return 1;
  try{if(samples&&count>0)currentWave->append(samples,count);return generation.load()==currentWave->token?0:1;}
  catch(...){callbackError=true;return 1;}
}
void fail(JNIEnv* env,const std::exception& error){env->ThrowNew(env->FindClass("java/lang/IllegalStateException"),error.what());}
}

extern "C" JNIEXPORT jlong JNICALL
Java_com_freebiblereader_speech_SpeechBridge_nativeBegin(JNIEnv*,jclass){return ++generation;}
extern "C" JNIEXPORT void JNICALL
Java_com_freebiblereader_speech_SpeechBridge_nativeCancel(JNIEnv*,jclass){++generation;}
extern "C" JNIEXPORT jstring JNICALL
Java_com_freebiblereader_speech_SpeechBridge_nativeSynthesize(JNIEnv* env,jclass,jstring providerValue,jstring voiceValue,jstring modelValue,jstring configValue,jstring dataValue,jbyteArray textValue,jdouble speed,jstring outputValue,jlong token){
  try{
    std::lock_guard<std::mutex> guard(bridgeMutex);
    std::lock_guard<std::mutex> espeakGuard(piper_jni::EspeakProcessMutex());
    if(generation.load()!=uint64_t(token))throw std::runtime_error("CANCELLED");
    const std::string provider=str(env,providerValue),voice=str(env,voiceValue),model=str(env,modelValue),config=str(env,configValue),data=str(env,dataValue),text=bytes(env,textValue),output=str(env,outputValue);
    if(text.empty()||text.size()>100000||speed<0.5||speed>2.2)throw std::runtime_error("INVALID_SPEECH_REQUEST");
    Wave wav(output,token);
    if(provider=="piper"){
      if(!cached||cachedModel!=model){
        cached.reset();cachedModel.clear();piper_create_options create;piper_init_create_options(&create);create.model_path=model.c_str();create.config_path=config.c_str();create.espeak_data_path=data.c_str();
        cached.reset(piper_create_with_options(&create));if(!cached)throw std::runtime_error("VOICE_LOAD_FAILED");cachedModel=model;
      }
      auto options=piper_default_synthesize_options(cached.get());options.length_scale=float(1.0/speed);
      if(piper_synthesize_start(cached.get(),text.c_str(),&options)!=PIPER_OK)throw std::runtime_error("PIPER_SYNTHESIS_FAILED");
      piper_audio_chunk chunk{};int status;
      do {
        chunk={};status=piper_synthesize_next(cached.get(),&chunk);
        if(status!=PIPER_OK&&status!=PIPER_DONE)throw std::runtime_error("PIPER_SYNTHESIS_FAILED");
        // libpiper returns PIPER_DONE WITH the final audio chunk. Discarding it
        // loses the last sentence, or all audio for a single-sentence passage.
        if(chunk.samples&&chunk.num_samples){wav.rate=chunk.sample_rate;wav.append(chunk.samples,chunk.num_samples);wav.modelChunks++;if(status==PIPER_DONE)wav.finalChunkSamples=chunk.num_samples;}
      } while(status!=PIPER_DONE);
    } else if(provider=="espeak-ng"){
      cached.reset();cachedModel.clear();
      const int rate=espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS,0,data.c_str(),espeakINITIALIZE_DONT_EXIT);if(rate<=0)throw std::runtime_error("ESPEAK_INITIALIZATION_FAILED");
      wav.rate=rate;callbackError=false;currentWave=&wav;espeak_SetSynthCallback(espeakCallback);
      if(espeak_SetVoiceByName(voice.c_str())!=EE_OK){currentWave=nullptr;espeak_Terminate();throw std::runtime_error("VOICE_NOT_INSTALLED_OR_CORRUPT");}
      espeak_SetParameter(espeakRATE,int(175*speed),0);
      const auto status=espeak_Synth(text.c_str(),text.size()+1,0,POS_CHARACTER,0,espeakCHARS_UTF8|espeakENDPAUSE,nullptr,nullptr);
      espeak_Synchronize();currentWave=nullptr;espeak_Terminate();
      if(generation.load()!=uint64_t(token))throw std::runtime_error("CANCELLED");
      if(status!=EE_OK||callbackError)throw std::runtime_error("ESPEAK_SYNTHESIS_FAILED");
    }else throw std::runtime_error("UNSUPPORTED_SPEECH_PROVIDER");
    const auto result=wav.finish();return env->NewStringUTF(result.c_str());
  }catch(const std::exception& error){currentWave=nullptr;fail(env,error);return nullptr;}
}
extern "C" JNIEXPORT void JNICALL
Java_com_freebiblereader_speech_SpeechBridge_nativeShutdown(JNIEnv*,jclass){++generation;std::lock_guard<std::mutex> guard(bridgeMutex);std::lock_guard<std::mutex> espeakGuard(piper_jni::EspeakProcessMutex());cached.reset();cachedModel.clear();}
extern "C" JNIEXPORT jboolean JNICALL
Java_com_freebiblereader_speech_SpeechBridge_nativeCanVoice(JNIEnv* env,jclass,jstring dataValue,jstring voiceValue){
  std::lock_guard<std::mutex> guard(bridgeMutex);std::lock_guard<std::mutex> espeakGuard(piper_jni::EspeakProcessMutex());
  cached.reset();cachedModel.clear();const std::string data=str(env,dataValue),voice=str(env,voiceValue);
  if(espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS,0,data.c_str(),espeakINITIALIZE_DONT_EXIT)<=0)return false;
  const bool ok=espeak_SetVoiceByName(voice.c_str())==EE_OK;espeak_Terminate();return ok;
}
