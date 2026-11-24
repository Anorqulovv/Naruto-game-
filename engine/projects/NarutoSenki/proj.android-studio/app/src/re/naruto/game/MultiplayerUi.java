package re.naruto.game;

import android.app.Activity;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.BitmapDrawable;
import android.graphics.drawable.ClipDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.LayerDrawable;
import android.net.wifi.WifiManager;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.view.animation.LinearInterpolator;

import java.io.InputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Wi-Fi multiplayer lobby (up to 6 players) in a ninja-scroll style, plus the client's own-hero
 * panel during a battle.
 *  - one phone opens a room, the others join (rooms are found automatically on the Wi-Fi);
 *  - every player who joins chooses: with the host's team or against it;
 *  - then everybody goes to Free Battle, picks a hero and presses Start.
 */
public final class MultiplayerUi {

    // implemented in Classes/Mp/Mp.cpp
    static native String nativeMpStatus();
    static native String nativeBusy();
    static native void nativeMpConfigure(int role, String ip);
    static native int nativeMpTeam();
    static native void nativeMpSetTeam(int team);
    static native void nativeAppPaused(boolean paused);

    private static final int DISCOVERY_PORT = 7778;
    private static final String TAG = "ROTN-ROOM";

    // ninja palette
    private static final int ORANGE = 0xFFFF7A00;
    private static final int ORANGE_LIGHT = 0xFFFFB03A;
    private static final int INK = 0xFF120A06;
    private static final int PAPER = 0xFFF3E2C0;

    private final Activity act;
    private final FrameLayout root;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private TextView launcher, status;
    private View panel;                    // the open lobby panel (one at a time)
    private LinearLayout heroPanel;
    private TextView heroName, heroInfo;
    private ProgressBar hpBar, ckrBar, ckr2Bar;
    private volatile boolean hosting;
    private String lastStatus = "";
    private FrameLayout loader;
    private TextView loaderText, teamChip;
    private long busySince = 0;
    private long statusShownAt = 0;
    private Typeface bold;

    private MultiplayerUi(Activity a, FrameLayout r) { act = a; root = r; }

    private static MultiplayerUi sInstance;

    public static void attach(Activity a, FrameLayout root) {
        sInstance = new MultiplayerUi(a, root);
        sInstance.build();
        // testing: adb shell setprop debug.rotn.mp host | client:IP | clientvs:IP
        try {
            String p = (String) Class.forName("android.os.SystemProperties").getMethod("get", String.class).invoke(null, "debug.rotn.mp");
            if ("host".equals(p)) nativeMpConfigure(1, null);
            else if (p != null && p.startsWith("client:")) nativeMpConfigure(2, p.substring(7));
            else if (p != null && p.startsWith("clientvs:")) nativeMpConfigure(4, p.substring(9));
        } catch (Throwable ignored) { }
    }

    /** The game's "Online Battle" entry opens the lobby (no extra button on screen). */
    public static void openLobby() {
        final MultiplayerUi m = sInstance;
        if (m == null) return;
        m.act.runOnUiThread(() -> {                  // called from the game (GL) thread
            if (m.panel != null) return;
            if (m.lobbyBusy()) { m.showRoom(); return; }
            m.showMenu();
        });
    }

    /** Already in a room: show where we are and allow leaving it. */
    private void showRoom() {
        LinearLayout c = openPanel("Online Battle", null);
        c.addView(label(translate(nativeMpStatus()), 14, PAPER, false));
        c.addView(buttonRow(
                ninjaButton("Xonadan chiqish", false, v -> { nativeMpConfigure(0, null); hosting = false; closePanel(); }),
                ninjaButton("Yopish", true, v -> closePanel())));
    }

    private boolean lobbyBusy() {
        String st;
        try { st = nativeMpStatus(); } catch (Throwable t) { return false; }
        if (st == null || st.equals("off")) return false;
        return !(st.startsWith("the host left") || st.startsWith("mode mismatch") || st.startsWith("could not reach")
                || st.startsWith("cannot open") || st.startsWith("the room is full") || st.startsWith("everybody left"));
    }

    private int dp(float v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, act.getResources().getDisplayMetrics());
    }

    // ------------------------------------------------------------------ style helpers
    private GradientDrawable rounded(int fill, int stroke, float radius, int strokeW) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill); g.setCornerRadius(dp(radius));
        if (strokeW > 0) g.setStroke(dp(strokeW), stroke);
        return g;
    }

    private Drawable scrollBackground() {
        Drawable tex = null;
        try (InputStream in = act.getAssets().open("red_bg.png")) {
            Bitmap b = BitmapFactory.decodeStream(in);
            BitmapDrawable bd = new BitmapDrawable(act.getResources(), b);
            bd.setTileModeXY(Shader.TileMode.MIRROR, Shader.TileMode.MIRROR);
            tex = bd;
        } catch (Exception ignored) { }
        GradientDrawable shade = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{0xCC1A0505, 0xE6140404, 0xF00A0202});
        shade.setCornerRadius(dp(14));
        GradientDrawable frame = rounded(Color.TRANSPARENT, ORANGE, 14, 3);
        Drawable[] layers = tex != null ? new Drawable[]{tex, shade, frame} : new Drawable[]{shade, frame};
        return new LayerDrawable(layers);
    }

    private TextView label(String text, float sp, int color, boolean heavy) {
        TextView t = new TextView(act);
        t.setText(text);
        t.setTextSize(sp);
        t.setTextColor(color);
        if (heavy) t.setTypeface(bold);
        t.setShadowLayer(dp(2), dp(1), dp(1), Color.BLACK);
        return t;
    }

    private TextView ninjaButton(String text, boolean primary, View.OnClickListener l) {
        final TextView b = label(text, 15, Color.WHITE, true);
        b.setGravity(Gravity.CENTER);
        b.setPadding(dp(18), dp(10), dp(18), dp(10));
        final GradientDrawable up = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                primary ? new int[]{ORANGE_LIGHT, ORANGE, 0xFFC23B00} : new int[]{0xFF4A2A1A, 0xFF2A140A, 0xFF1A0A04});
        up.setCornerRadius(dp(8)); up.setStroke(dp(2), primary ? INK : ORANGE);
        final GradientDrawable down = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{0xFFC23B00, 0xFF8A2200, 0xFF5A1400});
        down.setCornerRadius(dp(8)); down.setStroke(dp(2), ORANGE_LIGHT);
        b.setBackground(up);
        b.setOnTouchListener((v, e) -> {
            if (e.getAction() == MotionEvent.ACTION_DOWN) v.setBackground(down);
            else if (e.getAction() == MotionEvent.ACTION_UP || e.getAction() == MotionEvent.ACTION_CANCEL) v.setBackground(up);
            return false;
        });
        b.setOnClickListener(l);
        return b;
    }

    private View divider() {
        View v = new View(act);
        GradientDrawable g = new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT,
                new int[]{Color.TRANSPARENT, ORANGE, Color.TRANSPARENT});
        v.setBackground(g);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(2));
        lp.setMargins(0, dp(6), 0, dp(10));
        v.setLayoutParams(lp);
        return v;
    }

    /** A centered scroll-style panel over a dimmed screen. */
    private LinearLayout openPanel(String title, String subtitle) {
        closePanel();
        FrameLayout dim = new FrameLayout(act);
        dim.setBackgroundColor(0xA0000000);
        dim.setClickable(true);
        LinearLayout card = new LinearLayout(act);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackground(scrollBackground());
        card.setPadding(dp(22), dp(16), dp(22), dp(18));

        LinearLayout head = new LinearLayout(act);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        TextView mark = label("忍", 26, ORANGE, true);         // "shinobi"
        mark.setPadding(0, 0, dp(10), 0);
        head.addView(mark);
        LinearLayout titles = new LinearLayout(act);
        titles.setOrientation(LinearLayout.VERTICAL);
        titles.addView(label(title, 20, ORANGE_LIGHT, true));
        if (subtitle != null) titles.addView(label(subtitle, 12, PAPER, false));
        head.addView(titles);
        card.addView(head);
        card.addView(divider());

        ScrollView sv = new ScrollView(act);
        sv.addView(card);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(Math.min(dp(460), root.getWidth() - dp(24)),
                ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER);
        dim.addView(sv, lp);
        root.addView(dim, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        dim.setAlpha(0f); dim.animate().alpha(1f).setDuration(180).start();
        sv.setScaleX(0.9f); sv.setScaleY(0.9f); sv.animate().scaleX(1f).scaleY(1f).setDuration(180).start();
        panel = dim;
        return card;
    }

    private void closePanel() {
        if (panel != null) {
            View p = panel; panel = null;
            InputMethodManager imm = (InputMethodManager) act.getSystemService(Context.INPUT_METHOD_SERVICE);
            if (imm != null) imm.hideSoftInputFromWindow(p.getWindowToken(), 0);
            root.removeView(p);
        }
    }

    private LinearLayout buttonRow(View... buttons) {
        LinearLayout row = new LinearLayout(act);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        for (View b : buttons) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1);
            lp.setMargins(dp(5), dp(12), dp(5), 0);
            row.addView(b, lp);
        }
        return row;
    }

    // ------------------------------------------------------------------ build
    private void build() {
        bold = Typeface.create(Typeface.SERIF, Typeface.BOLD_ITALIC);

        launcher = label("忍  Wi-Fi jang", 13, Color.WHITE, true);
        launcher.setPadding(dp(12), dp(6), dp(12), dp(6));
        GradientDrawable lb = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{0xE6FF8A1A, 0xE6C23B00});
        lb.setCornerRadius(dp(18)); lb.setStroke(dp(2), INK);
        launcher.setBackground(lb);
        launcher.setOnClickListener(v -> showMenu());
        launcher.setVisibility(View.GONE);          // the lobby opens from the game's own "Online Battle" entry
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP | Gravity.END);
        lp.setMargins(0, dp(6), dp(6), 0);
        root.addView(launcher, lp);

        status = label("", 12, Color.WHITE, true);
        status.setBackground(rounded(0xB0120604, ORANGE, 8, 1));
        status.setPadding(dp(10), dp(4), dp(10), dp(4));
        status.setMaxWidth(dp(280));
        status.setVisibility(View.GONE);
        FrameLayout.LayoutParams slp = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP | Gravity.END);
        slp.setMargins(0, dp(44), dp(6), 0);
        root.addView(status, slp);

        buildHeroPanel();
        buildLoader();
        buildTeamChip();
        poll();
        pollBusy();
    }

    private ProgressBar bar(int c1, int c2) {
        ProgressBar p = new ProgressBar(act, null, android.R.attr.progressBarStyleHorizontal);
        p.setMax(1000);
        GradientDrawable back = rounded(0xAA000000, 0xFF000000, 4, 1);
        GradientDrawable fill = new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, new int[]{c1, c2});
        fill.setCornerRadius(dp(4));
        LayerDrawable ld = new LayerDrawable(new Drawable[]{back, new ClipDrawable(fill, Gravity.START, ClipDrawable.HORIZONTAL)});
        ld.setId(0, android.R.id.background); ld.setId(1, android.R.id.progress);
        p.setProgressDrawable(ld);
        return p;
    }

    private void buildHeroPanel() {
        heroPanel = new LinearLayout(act);
        heroPanel.setOrientation(LinearLayout.VERTICAL);
        heroPanel.setBackground(rounded(0xB0120604, ORANGE, 10, 2));
        heroPanel.setPadding(dp(10), dp(6), dp(10), dp(8));
        heroName = label("", 14, ORANGE_LIGHT, true);
        heroInfo = label("", 11, PAPER, true);
        LinearLayout top = new LinearLayout(act);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.addView(heroName);
        View sp = new View(act);
        top.addView(sp, new LinearLayout.LayoutParams(0, 1, 1));
        top.addView(heroInfo);
        heroPanel.addView(top);
        hpBar = bar(0xFF1FD15A, 0xFF9BFF5A);
        ckrBar = bar(0xFF1A6CFF, 0xFF5AD0FF);
        ckr2Bar = bar(0xFF8A2BE2, 0xFFE05AFF);
        int[] h = {dp(9), dp(6), dp(6)};
        ProgressBar[] bars = {hpBar, ckrBar, ckr2Bar};
        for (int i = 0; i < 3; i++) {
            LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, h[i]);
            blp.setMargins(0, dp(4), 0, 0);
            heroPanel.addView(bars[i], blp);
        }
        heroPanel.setVisibility(View.GONE);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(dp(210), ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        lp.setMargins(0, 0, 0, dp(8));
        root.addView(heroPanel, lp);
    }

    // ------------------------------------------------------------------ loader (shuriken)
    private final class Shuriken extends View {
        private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG), hole = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Path star = new Path();
        Shuriken(Context c) {
            super(c);
            fill.setColor(0xFFD8D8E0); fill.setShadowLayer(dp(4), 0, 0, ORANGE);
            hole.setColor(INK);
            setLayerType(View.LAYER_TYPE_SOFTWARE, null);
        }
        @Override protected void onDraw(Canvas cv) {
            float w = getWidth(), h = getHeight(), cx = w / 2, cy = h / 2, R = Math.min(w, h) / 2 - dp(4), r = R * 0.28f;
            star.reset();
            for (int i = 0; i < 8; i++) {                       // 4-pointed ninja star
                double a = Math.PI / 4 * i - Math.PI / 2;
                float rad = (i % 2 == 0) ? R : r;
                float x = cx + (float) Math.cos(a) * rad, y = cy + (float) Math.sin(a) * rad;
                if (i == 0) star.moveTo(x, y); else star.lineTo(x, y);
            }
            star.close();
            cv.drawPath(star, fill);
            cv.drawCircle(cx, cy, r * 0.45f, hole);
        }
    }

    private void buildLoader() {
        loader = new FrameLayout(act);
        loader.setBackgroundColor(0x66000000);
        LinearLayout box = new LinearLayout(act);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER_HORIZONTAL);
        Shuriken s = new Shuriken(act);
        box.addView(s, new LinearLayout.LayoutParams(dp(72), dp(72)));
        ObjectAnimator spin = ObjectAnimator.ofFloat(s, "rotation", 0f, 360f);
        spin.setDuration(900); spin.setRepeatCount(ValueAnimator.INFINITE); spin.setInterpolator(new LinearInterpolator());
        spin.start();
        loaderText = label("Yuklanmoqda...", 15, ORANGE_LIGHT, true);
        loaderText.setGravity(Gravity.CENTER);
        loaderText.setPadding(0, dp(10), 0, 0);
        loaderText.setMaxWidth(dp(320));
        // only the spinning shuriken is shown (no frame, no text)
        loader.addView(box, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER));
        loader.setVisibility(View.GONE);
        root.addView(loader, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    private void pollBusy() {
        ui.postDelayed(new Runnable() {
            @Override public void run() {
                String b;
                try { b = nativeBusy(); } catch (Throwable t) { b = ""; }
                long now = System.currentTimeMillis();
                if (b == null || b.isEmpty() || panel != null) { busySince = 0; loader.setVisibility(View.GONE); }
                else {
                    if (busySince == 0) busySince = now;
                    if (now - busySince > 300) {                  // short hiccups don't flash the loader
                        loaderText.setText(busyText(b));
                        if (loader.getVisibility() != View.VISIBLE) { loader.setAlpha(0f); loader.setVisibility(View.VISIBLE); loader.animate().alpha(1f).setDuration(150).start(); }
                    }
                }
                ui.postDelayed(this, 150);
            }
        }, 1000);
    }

    private static String busyText(String b) {
        switch (b) {
            case "wait:players": return "Boshqa o'yinchilar Start bosishi kutilmoqda...";
            case "wait:host": return "Xona egasi Start bosishi kutilmoqda...";
            case "wait:net": return "Tarmoq sekin — o'yinchilar kutilmoqda...";
            default: return "Yuklanmoqda...";
        }
    }

    // ------------------------------------------------------------------ team chip (client, before the battle)
    private void buildTeamChip() {
        teamChip = label("", 13, Color.WHITE, true);
        teamChip.setPadding(dp(12), dp(6), dp(12), dp(6));
        teamChip.setVisibility(View.GONE);
        teamChip.setOnClickListener(v -> {
            int t = nativeMpTeam() == 0 ? 1 : 0;
            nativeMpSetTeam(t);
            refreshTeamChip();
        });
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP | Gravity.END);
        lp.setMargins(0, dp(82), dp(6), 0);
        root.addView(teamChip, lp);
    }

    private void refreshTeamChip() {
        boolean rival = nativeMpTeam() == 1;
        teamChip.setText("Jamoa: " + (rival ? "Raqib" : "Sherik") + "   ⇄");
        GradientDrawable g = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                rival ? new int[]{0xE6D02A2A, 0xE6801010} : new int[]{0xE62A8AD0, 0xE6104A80});
        g.setCornerRadius(dp(16)); g.setStroke(dp(2), ORANGE);
        teamChip.setBackground(g);
    }

    // ------------------------------------------------------------------ lobby screens
    private void showMenu() {
        LinearLayout c = openPanel("Online Battle", "Wi-Fi orqali · 2–6 o'yinchi");
        TextView t = label("Bir o'yinchi xona ochadi, qolganlar qo'shiladi.\n"
                + "Keyin hamma Free Battle → rejim → qahramon → Start bosadi.\n"
                + "Rejimni (1v1, 2v2, 3v3) xona egasi tanlaydi.\n"
                + "Bo'sh o'rinlarni botlar egallaydi.", 14, PAPER, false);
        t.setLineSpacing(0, 1.15f);
        c.addView(t);
        c.addView(buttonRow(
                ninjaButton("Xona ochish", true, v -> host()),
                ninjaButton("Qo'shilish", true, v -> join())));
        c.addView(buttonRow(ninjaButton("Yopish", false, v -> closePanel())));
    }

    private void host() {
        nativeMpConfigure(1, null);
        hosting = true;
        startBeacon();
        String ip = localIp();
        LinearLayout c = openPanel("Xona ochildi", "Do'stlaringiz \"Qo'shilish\" ni bossin");
        c.addView(label("Sizning IP manzilingiz", 12, PAPER, false));
        TextView ipv = label(ip == null ? "Wi-Fi topilmadi" : ip, 28, ORANGE_LIGHT, true);
        ipv.setPadding(0, dp(2), 0, dp(8));
        c.addView(ipv);
        final TextView joined = label("O'yinchilar kutilmoqda...", 15, Color.WHITE, true);
        c.addView(joined);
        c.addView(label("Hamma qo'shilgach: Free Battle → rejim → qahramon → Start.\n"
                + "Har bir o'yinchi sherik yoki raqib bo'lishni o'zi tanlaydi va\n"
                + "jang boshlanguncha istalgan payt almashtira oladi.", 13, PAPER, false));
        c.addView(buttonRow(ninjaButton("Tushunarli", true, v -> closePanel())));
        ui.post(new Runnable() {
            @Override public void run() {
                if (panel == null) return;
                String st = nativeMpStatus();
                if (st.startsWith("room open: ")) joined.setText(roomText(st, false));
                ui.postDelayed(this, 700);
            }
        });
    }

    private void join() {
        final LinearLayout c = openPanel("Xonaga qo'shilish", "Tarmoqdagi xonalar avtomatik qidiriladi");
        final int[] team = {0};
        c.addView(label("Jamoangiz", 13, PAPER, false));
        final TextView ally = ninjaButton("Sherik", true, null);
        final TextView rival = ninjaButton("Raqib", true, null);
        View.OnClickListener pick = v -> {
            team[0] = v == rival ? 1 : 0;
            ally.setAlpha(team[0] == 0 ? 1f : 0.4f);
            rival.setAlpha(team[0] == 1 ? 1f : 0.4f);
        };
        ally.setOnClickListener(pick); rival.setOnClickListener(pick);
        rival.setAlpha(0.4f);
        c.addView(buttonRow(ally, rival));
        c.addView(divider());
        final TextView hint = label("Xonalar qidirilmoqda...", 14, Color.WHITE, true);
        c.addView(hint);
        final LinearLayout list = new LinearLayout(act);
        list.setOrientation(LinearLayout.VERTICAL);
        c.addView(list);
        final EditText ipField = new EditText(act);
        ipField.setHint("yoki IP manzil: 192.168.1.5");
        ipField.setHintTextColor(0x99F3E2C0);
        ipField.setTextColor(Color.WHITE);
        ipField.setInputType(InputType.TYPE_CLASS_PHONE);
        ipField.setBackground(rounded(0x66000000, ORANGE, 6, 1));
        ipField.setPadding(dp(10), dp(8), dp(10), dp(8));
        LinearLayout.LayoutParams ilp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        ilp.setMargins(0, dp(10), 0, 0);
        c.addView(ipField, ilp);
        c.addView(buttonRow(
                ninjaButton("Ulanish", true, v -> {
                    String ip = ipField.getText().toString().trim();
                    if (!ip.isEmpty()) connect(ip, team[0]);
                }),
                ninjaButton("Bekor", false, v -> closePanel())));
        final List<String> seen = new ArrayList<>();
        listenForRooms(seen, (name, ip) -> {
            hint.setText("Topilgan xonalar — tanlang:");
            TextView room = ninjaButton("忍 " + name + "   " + ip, false, v -> connect(ip, team[0]));
            room.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
            LinearLayout.LayoutParams rlp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            rlp.setMargins(0, dp(6), 0, 0);
            list.addView(room, rlp);
        }, () -> { if (seen.isEmpty()) hint.setText("Xona topilmadi — IP manzilni kiriting."); });
    }

    private void connect(String ip, int team) {
        nativeMpConfigure(team == 1 ? 4 : 2, ip);
        closePanel();
    }

    // ------------------------------------------------------------------ LAN discovery (UDP broadcast)
    private void startBeacon() {
        new Thread(() -> {
            try (DatagramSocket s = new DatagramSocket()) {
                s.setBroadcast(true);
                byte[] msg = (TAG + "|" + android.os.Build.MODEL).getBytes("UTF-8");
                InetAddress bc = InetAddress.getByName("255.255.255.255");
                while (hosting) {
                    String st = nativeMpStatus();
                    if (st.startsWith("room open")) s.send(new DatagramPacket(msg, msg.length, bc, DISCOVERY_PORT));
                    Thread.sleep(1000);
                }
            } catch (Exception ignored) { }
        }).start();
    }

    private interface RoomFound { void found(String name, String ip); }

    private void listenForRooms(final List<String> seen, final RoomFound cb, final Runnable done) {
        new Thread(() -> {
            WifiManager wm = (WifiManager) act.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            WifiManager.MulticastLock lock = wm != null ? wm.createMulticastLock("rotn") : null;
            if (lock != null) lock.acquire();
            try (DatagramSocket s = new DatagramSocket(null)) {
                s.setReuseAddress(true);
                s.bind(new InetSocketAddress(DISCOVERY_PORT));
                s.setSoTimeout(1000);
                byte[] buf = new byte[256];
                long end = System.currentTimeMillis() + 30000;
                while (System.currentTimeMillis() < end && panel != null) {
                    try {
                        DatagramPacket p = new DatagramPacket(buf, buf.length);
                        s.receive(p);
                        String m = new String(p.getData(), 0, p.getLength(), "UTF-8");
                        if (!m.startsWith(TAG + "|")) continue;
                        final String name = m.substring(TAG.length() + 1), ip = p.getAddress().getHostAddress();
                        if (seen.contains(ip)) continue;
                        seen.add(ip);
                        ui.post(() -> cb.found(name, ip));
                    } catch (java.net.SocketTimeoutException ignored) { }
                }
            } catch (Exception ignored) {
            } finally {
                if (lock != null) lock.release();
                ui.post(done);
            }
        }).start();
    }

    // ------------------------------------------------------------------ status + own-hero panel
    private void poll() {
        ui.postDelayed(new Runnable() {
            @Override public void run() {
                String st;
                try { st = nativeMpStatus(); } catch (Throwable t) { st = "off"; }
                boolean off = st == null || st.equals("off");
                if (!st.equals(lastStatus)) { lastStatus = st; statusShownAt = System.currentTimeMillis(); }
                // in a battle the line hides after a few seconds (it would cover the game's counters)
                boolean stale = st.startsWith("battle") && System.currentTimeMillis() - statusShownAt > 5000;
                if (off || stale) status.setVisibility(View.GONE);
                else { status.setVisibility(View.VISIBLE); status.setText(translate(st)); }
                boolean over = off || st.startsWith("the host left") || st.startsWith("mode mismatch")
                        || st.startsWith("could not reach") || st.startsWith("cannot open")
                        || st.startsWith("the room is full") || st.startsWith("everybody left");
                if (over) hosting = false;
                launcher.setVisibility(View.GONE);
                boolean inRoom = st.startsWith("connected") || st.startsWith("waiting for the host");
                if (inRoom && teamChip.getVisibility() != View.VISIBLE) refreshTeamChip();
                teamChip.setVisibility(inRoom && panel == null ? View.VISIBLE : View.GONE);
                updateHeroPanel();
                ui.postDelayed(this, 250);
            }
        }, 500);
    }

    private void updateHeroPanel() {
        String h;
        h = "";   // RotN 2.2: the game's own HUD shows the player's hero
        if (h == null || h.isEmpty()) { heroPanel.setVisibility(View.GONE); return; }
        String[] f = h.split("\\|");
        if (f.length < 7) return;
        heroPanel.setVisibility(View.VISIBLE);
        heroName.setText(f[0]);
        heroInfo.setText((f[6].equals("1") ? "Raqib" : "Sherik") + "  ·  LV " + f[4] + "  ·  ⚔ " + f[5]);
        hpBar.setProgress(clamp(f[1]));
        ckrBar.setProgress(clamp(f[2]));
        ckr2Bar.setProgress(clamp(f[3]));
    }

    private static int clamp(String v) {
        try { return Math.max(0, Math.min(1000, (int) (Float.parseFloat(v) * 1000))); } catch (Exception e) { return 0; }
    }

    /** "room open: N players joined A B" -> readable text */
    private static String roomText(String st, boolean shortForm) {
        String[] p = st.substring(11).split(" ");
        String n = p[0], a = p.length > 4 ? p[3] : "?", b = p.length > 4 ? p[4] : "?";
        if (n.equals("0")) return shortForm ? "忍 Xona ochiq — o'yinchilar kutilmoqda" : "O'yinchilar kutilmoqda...";
        String teams = "sherik: " + a + ", raqib: " + b;
        return shortForm ? "忍 Xonada " + n + " o'yinchi (" + teams + ") · Free Battle → Start"
                         : "Qo'shilganlar: " + n + " ta o'yinchi\n" + teams;
    }

    private static String translate(String st) {
        if (st.startsWith("room open: ")) return roomText(st, true);
        if (st.startsWith("connecting")) return "Ulanmoqda...";
        if (st.startsWith("connected")) return "忍 Xonaga ulandingiz! Free Battle → Start";
        if (st.startsWith("waiting for the players")) return "Boshqalar Start bosishi kutilmoqda...";
        if (st.startsWith("waiting for the host")) return "Xona egasi Start bosishi kutilmoqda...";
        if (st.startsWith("battle: ")) {
            String r = st.substring(8);
            String n = r.split(" ")[0];
            if (r.contains("you are the host")) return "⚔ Wi-Fi jang · " + n + " o'yinchi · siz xona egasisiz";
            if (r.contains("(rival)")) return "⚔ Wi-Fi jang · " + n + " o'yinchi · siz raqib jamoadasiz";
            if (r.contains("(team)")) return "⚔ Wi-Fi jang · " + n + " o'yinchi · siz sherik jamoadasiz";
            if (r.contains("watching")) return "Bo'sh joy qolmadi — siz tomoshabinsiz";
            return "⚔ Wi-Fi jang";
        }
        if (st.startsWith("the host left the room")) return "Xona egasi xonani yopdi";
        if (st.startsWith("the host left")) return "Xona egasi chiqib ketdi — botlar bilan davom etasiz";
        if (st.startsWith("everybody left")) return "Hamma chiqib ketdi — botlar bilan davom etasiz";
        if (st.startsWith("mode mismatch")) return "Hamma bir xil rejimni tanlashi kerak!";
        if (st.startsWith("warning")) return "Ogohlantirish: o'yinlar sinxronligi buzildi";
        if (st.startsWith("could not reach")) return "Xonaga ulanib bo'lmadi";
        if (st.startsWith("the room is full")) return "Xona to'la yoki jang allaqachon boshlangan";
        if (st.startsWith("cannot open")) return "Xona ochib bo'lmadi";
        return st;
    }

    private static String localIp() {
        try {
            for (NetworkInterface ni : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!ni.isUp() || ni.isLoopback()) continue;
                for (InetAddress a : Collections.list(ni.getInetAddresses()))
                    if (a instanceof Inet4Address && !a.isLoopbackAddress()
                            && (ni.getName().startsWith("wlan") || ni.getName().startsWith("eth"))) return a.getHostAddress();
            }
        } catch (Exception ignored) { }
        return null;
    }
}
