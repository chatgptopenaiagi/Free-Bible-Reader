// First-party JNI adapter; linked eSpeak NG retains GPL-3.0-or-later terms.
#include <jni.h>
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <mutex>
#include <stdexcept>
#include <string>
#include "espeak-ng/speak_lib.h"

namespace {
std::mutex engine;
std::atomic<uint64_t> generation{0};
struct Sink { JNIEnv* env; jobject object; jmethodID audio; uint64_t token; uint64_t samples=0; int peak=0; bool stopped=false; bool limit=false; };
thread_local Sink* active=nullptr;
std::string string(JNIEnv* env,jstring value){
    if(!value)throw std::runtime_error("DATA_PATH_REQUIRED");
    const char* chars=env->GetStringUTFChars(value,nullptr);
    if(!chars)throw std::runtime_error("UTF8_ALLOCATION_FAILED");
    std::string out(chars);env->ReleaseStringUTFChars(value,chars);return out;
}
int audio(short* values,int count,espeak_EVENT*){
    if(!active)return 1;
    auto& s=*active;
    if(generation.load()!=s.token){s.stopped=true;return 1;}
    if(!values||count<=0)return 0;
    if(s.samples+uint64_t(count)>22050ULL*300){s.limit=true;return 1;}
    jbyteArray data=s.env->NewByteArray(count*2);
    if(!data)return 1;
    std::string bytes(count*2,'\0');
    for(int i=0;i<count;i++){const uint16_t sample=uint16_t(values[i]);bytes[2*i]=char(sample);bytes[2*i+1]=char(sample>>8);s.peak=std::max(s.peak,std::abs(int(values[i])));}
    s.env->SetByteArrayRegion(data,0,count*2,reinterpret_cast<const jbyte*>(bytes.data()));
    const bool ok=s.env->CallBooleanMethod(s.object,s.audio,data);
    s.env->DeleteLocalRef(data);
    if(s.env->ExceptionCheck()||!ok){s.stopped=true;return 1;}
    s.samples+=count;return 0;
}
struct Terminate { ~Terminate(){active=nullptr;espeak_Terminate();} };
void error(JNIEnv* env,const std::exception& e){if(!env->ExceptionCheck())env->ThrowNew(env->FindClass("java/lang/IllegalStateException"),e.what());}
int initialize(const std::string& path){
    const int rate=espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS,40,path.c_str(),espeakINITIALIZE_DONT_EXIT);
    if(rate<=0||espeak_SetVoiceByName("ro")!=EE_OK)throw std::runtime_error("ROMANIAN_VOICE_UNAVAILABLE");
    return rate;
}
}
extern "C" JNIEXPORT jlong JNICALL Java_com_freebiblereader_voice_ro_NativeVoice_begin(JNIEnv*,jclass){return ++generation;}
extern "C" JNIEXPORT void JNICALL Java_com_freebiblereader_voice_ro_NativeVoice_cancel(JNIEnv*,jclass){++generation;}
extern "C" JNIEXPORT jboolean JNICALL Java_com_freebiblereader_voice_ro_NativeVoice_validate(JNIEnv* env,jclass,jstring path){
    std::lock_guard<std::mutex> lock(engine);Terminate done;
    try{initialize(string(env,path));return true;}catch(const std::exception& e){error(env,e);return false;}
}
extern "C" JNIEXPORT jlong JNICALL Java_com_freebiblereader_voice_ro_NativeVoice_synthesize(JNIEnv* env,jclass,jstring path,jbyteArray input,jint rate,jint pitch,jobject sink,jlong token){
    std::lock_guard<std::mutex> lock(engine);Terminate done;
    try{
        if(generation.load()!=uint64_t(token))return -1;
        const int size=input?env->GetArrayLength(input):0;
        if(size<=0||size>32000||!sink)throw std::runtime_error("INVALID_SYNTHESIS_INPUT");
        std::string text(size,'\0');env->GetByteArrayRegion(input,0,size,reinterpret_cast<jbyte*>(text.data()));
        if(text.find('\0')!=std::string::npos)throw std::runtime_error("INVALID_SYNTHESIS_TEXT");
        const int sampleRate=initialize(string(env,path));
        espeak_SetParameter(espeakRATE,std::clamp(int(rate),80,450),0);
        espeak_SetParameter(espeakPITCH,std::clamp(int(pitch),0,99),0);
        jclass type=env->GetObjectClass(sink);
        jmethodID start=env->GetMethodID(type,"start","(I)Z"),emit=env->GetMethodID(type,"audio","([B)Z");
        if(!start||!emit||!env->CallBooleanMethod(sink,start,sampleRate))return -1;
        Sink current{env,sink,emit,uint64_t(token)};active=&current;espeak_SetSynthCallback(audio);
        const auto result=espeak_Synth(text.c_str(),text.size()+1,0,POS_CHARACTER,0,espeakCHARS_UTF8|espeakENDPAUSE,nullptr,nullptr);
        espeak_Synchronize();active=nullptr;
        if(current.limit)throw std::runtime_error("AUDIO_DURATION_LIMIT_CHOOSE_SMALLER_TEXT");
        if(current.stopped||generation.load()!=uint64_t(token))return -1;
        if(result!=EE_OK||current.samples==0||current.peak==0)throw std::runtime_error("SYNTHESIS_FAILED_OR_SILENT");
        return jlong(current.samples);
    }catch(const std::exception& e){error(env,e);return 0;}
}
