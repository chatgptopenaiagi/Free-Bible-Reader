@echo off
setlocal
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Android\openjdk\jdk-21.0.8"
if defined GRADLE_HOME if exist "%GRADLE_HOME%\bin\gradle.bat" (
 call "%GRADLE_HOME%\bin\gradle.bat" %*
 exit /b %ERRORLEVEL%
)
if exist "%USERPROFILE%\.gradle\wrapper\dists\gradle-9.3.1-bin\23ovyewtku6u96viwx3xl3oks\gradle-9.3.1\bin\gradle.bat" (
 call "%USERPROFILE%\.gradle\wrapper\dists\gradle-9.3.1-bin\23ovyewtku6u96viwx3xl3oks\gradle-9.3.1\bin\gradle.bat" %*
) else (
 echo Use Gradle 9.3.1 with JDK 21 to build this project.
 exit /b 1
)
