#!/bin/bash
# Rise of the Ninja 2.2: native arm64 Android build of the engine/ sources (based on NarutoSenki-V2).
#
# Optional, outside the repository:
#   ROTN_ASSETS=<dir>    original Rise of the Ninja assets: regenerates app/overlay (otherwise the committed one is used)
#   app/music/           extra menu/select/battle music (Audio/Music/menu_extra1.m4a, menu_extra2.mp3, menu_extra3.m4a)
#   KEYSTORE=<file>      signing key (alias rotn, password in KEYSTORE_PASS, default "android");
#                        without it a local key is created in app/build-key/ (other key = no update over old installs)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
V2="$HERE/../engine"
APPDIR="$V2/projects/NarutoSenki/proj.android-studio/app"
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
NDK="$(ls -d "$SDK"/ndk/* | sort -V | tail -1)"
BT="$(ls -d "$SDK"/build-tools/* | sort -V | tail -1)"
ANDROID_JAR="$(ls -d "$SDK"/platforms/android-* | sort -V | tail -1)/android.jar"
OUT="$HERE/build"; NOUT="$HERE/build-native"
APK_NAME="RiseOfTheNinja-2.2-arm64.apk"

"$NDK/ndk-build" -j10 NDK_PROJECT_PATH="$APPDIR" APP_BUILD_SCRIPT="$APPDIR/jni/Android.mk" \
  NDK_APPLICATION_MK="$APPDIR/jni/Application.mk" APP_ABI=arm64-v8a APP_PLATFORM=android-24 \
  NDK_OUT="$NOUT/obj" NDK_LIBS_OUT="$NOUT/libs" \
  "NDK_MODULE_PATH=$V2:$V2/cocos2dx:$V2/cocos2dx/platform/third_party/android/prebuilt:$V2/external:$V2/extensions:$V2/CocosDenshion/android" >/dev/null

rm -rf "$OUT"; mkdir -p "$OUT"/{res,classes,dex,stage/lib/arm64-v8a,stage/assets}
cp "$NOUT"/libs/arm64-v8a/*.so "$OUT/stage/lib/arm64-v8a/"
"$NDK"/toolchains/llvm/prebuilt/*/bin/llvm-strip "$OUT"/stage/lib/arm64-v8a/libcocos2dcpp.so
rsync -a --exclude '.DS_Store' "$V2/projects/NarutoSenki/Resources/" "$OUT/stage/assets/"
rsync -a "$V2/projects/NarutoSenki/lua/" "$OUT/stage/assets/lua/"
# RotN 2.2 look (title, menu cards, backgrounds) and the extra menu/select/battle music
if [ -n "${ROTN_ASSETS:-}" ]; then ROTN_ASSETS="$ROTN_ASSETS" python3 "$HERE/rotn_assets.py" >/dev/null; fi
rsync -a "$HERE/overlay/" "$OUT/stage/assets/"
rsync -a "$HERE/extra/" "$OUT/stage/assets/"
if [ -d "$HERE/music" ]; then rsync -a "$HERE/music/" "$OUT/stage/assets/"; fi
python3 "$HERE/tools/fix_plists.py" "$OUT/stage/assets" >/dev/null   # V2 atlases naming missing textures

"$BT/aapt2" compile --dir "$HERE/res" -o "$OUT/res/res.zip"
"$BT/aapt2" link -I "$ANDROID_JAR" --manifest "$HERE/AndroidManifest.xml" -A "$OUT/stage/assets" \
  -0 ogg -0 mp3 -0 wav -0 m4a --java "$OUT/gen" -o "$OUT/base.apk" "$OUT/res/res.zip"
find "$V2/cocos2dx/platform/android/java/src" "$APPDIR/src" "$OUT/gen" -name '*.java' > "$OUT/sources.txt"
javac --release 8 -nowarn -Xlint:-options -encoding UTF-8 -classpath "$ANDROID_JAR" -d "$OUT/classes" @"$OUT/sources.txt"
"$BT/d8" --release --min-api 24 --lib "$ANDROID_JAR" --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')
cp "$OUT/base.apk" "$OUT/unsigned.apk"
( cd "$OUT/dex" && zip -q -X "$OUT/unsigned.apk" classes.dex )
( cd "$OUT/stage" && zip -q -X -r "$OUT/unsigned.apk" lib )
"$BT/zipalign" -f -p 16 "$OUT/unsigned.apk" "$OUT/aligned.apk"
KS="${KEYSTORE:-$HERE/build-key/release.keystore}"; KP="${KEYSTORE_PASS:-android}"
if [ ! -f "$KS" ]; then
  mkdir -p "$(dirname "$KS")"
  keytool -genkeypair -keystore "$KS" -alias rotn -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass "$KP" -keypass "$KP" -dname "CN=Rise of the Ninja" >/dev/null 2>&1
fi
"$BT/apksigner" sign --ks "$KS" --ks-key-alias rotn --ks-pass pass:"$KP" --key-pass pass:"$KP" \
  --min-sdk-version 24 --out "$OUT/$APK_NAME" "$OUT/aligned.apk" 2>/dev/null
rm -f "$OUT/unsigned.apk" "$OUT/aligned.apk" "$OUT/base.apk"
echo "OK -> $OUT/$APK_NAME"
