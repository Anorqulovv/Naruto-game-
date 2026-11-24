package re.naruto.game;

import android.content.Context;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.WindowManager;

import org.cocos2dx.lib.Cocos2dxActivity;
import org.cocos2dx.lib.Cocos2dxGLSurfaceView;

public class NarutoSenki extends Cocos2dxActivity{
	protected void onCreate(Bundle savedInstanceState){
		super.onCreate(savedInstanceState);
		getWindow().setFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON, WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
		if (android.os.Build.VERSION.SDK_INT >= 28) {
			WindowManager.LayoutParams lp = getWindow().getAttributes();
			lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
			getWindow().setAttributes(lp);
		}
		hideSystemUi();
		// RotN 2.2: Wi-Fi room lobby (opened from the menu's Online Battle card)
		final android.widget.FrameLayout root = (android.widget.FrameLayout) findViewById(android.R.id.content);
		root.post(() -> MultiplayerUi.attach(this, root));
	}

	@Override
	protected void onPause() {
		super.onPause();
		try { MultiplayerUi.nativeAppPaused(true); } catch (Throwable ignored) { }
	}

	@Override
	protected void onResume() {
		super.onResume();
		try { MultiplayerUi.nativeAppPaused(false); } catch (Throwable ignored) { }
	}

	@Override
	public void onWindowFocusChanged(boolean hasFocus) {
		super.onWindowFocusChanged(hasFocus);
		if (hasFocus) hideSystemUi();
	}

	@SuppressWarnings("deprecation")
	private void hideSystemUi() {
		getWindow().getDecorView().setSystemUiVisibility(
				android.view.View.SYSTEM_UI_FLAG_LAYOUT_STABLE
				| android.view.View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
				| android.view.View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
				| android.view.View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
				| android.view.View.SYSTEM_UI_FLAG_FULLSCREEN
				| android.view.View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
	}

	public Cocos2dxGLSurfaceView onCreateGLSurfaceView() {
		return new LuaGLSurfaceView(this);
	}

     static {
         System.loadLibrary("cocos2dcpp");
     }
}

class LuaGLSurfaceView extends Cocos2dxGLSurfaceView{

	public LuaGLSurfaceView(Context context){
		super(context);
	}

	public boolean onKeyDown(int keyCode, KeyEvent event) {
		// exit program when key back is entered
		if (keyCode == KeyEvent.KEYCODE_BACK) {
			android.os.Process.killProcess(android.os.Process.myPid());
		}
		return super.onKeyDown(keyCode, event);
	}
}
