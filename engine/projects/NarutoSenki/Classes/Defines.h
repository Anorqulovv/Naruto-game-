#pragma once
#include "cocos2d.h"
#include "SimpleAudioEngine.h"

#include "Data/Types.h"
#include "Data/UnitDefines.h"
#include "Data/Version.h"
#include "Enums/Audio.hpp"
#include "Enums/Character.h"
#include "Utils/Utils.h"

using namespace cocos2d;
using namespace CocosDenshion;
using namespace std;

#define winSize Director::sharedDirector()->getWinSize()
// RotN 2.2: game-logic random numbers go through Mp (shared seed during a Wi-Fi battle)
int ns_random(int x);
void ns_setRand();
int ns_rand();
#define random(x) (ns_random(x))
#define setRand() ns_setRand()

#define is_same(__Str1, __Str2) (strcmp(__Str1, __Str2) == 0)
#define to_cstr(var) (std::to_string(var).c_str())
