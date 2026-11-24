APP_STL := c++_shared

APP_CPPFLAGS :=  -ftrivial-auto-var-init=zero -std=c++17 -include $(NDK_PROJECT_PATH)/jni/cxx20_polyfill.h -I$(NDK_PROJECT_PATH)/../../../../external -frtti -fsigned-char -fexceptions
APP_LDFLAGS := -latomic

APP_SHORT_COMMANDS := true

ifeq ($(NDK_DEBUG),1)
  APP_CPPFLAGS += -DNDEBUG -DCOCOS2D_DEBUG=1
else
  APP_CPPFLAGS += -DCOCOS2D_DEBUG=0
endif

# RotN 2.2: zero-initialised locals (Wi-Fi battle determinism)
APP_CFLAGS += -ftrivial-auto-var-init=zero
