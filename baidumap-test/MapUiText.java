import android.app.UiAutomation;
import android.os.Bundle;
import android.os.HandlerThread;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Base64;
import android.view.accessibility.AccessibilityNodeInfo;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/* One-shot shell helper: set Unicode text through the focused editable node.
 * It performs no clicks and installs no app, IME or accessibility service. */
public class MapUiText {
    private static void collect(AccessibilityNodeInfo node, List<AccessibilityNodeInfo> out) {
        if (node == null) return;
        if (node.isEditable() && node.isVisibleToUser()) out.add(node);
        for (int i = 0; i < node.getChildCount(); ++i) collect(node.getChild(i), out);
    }

    public static void main(String[] args) {
        HandlerThread thread = new HandlerThread("MapUiText");
        Object ui = null;
        int code = 1;
        try {
            if (args.length != 1) throw new IllegalArgumentException("Expected base64 UTF-8 text");
            String text = new String(Base64.decode(args[0], Base64.DEFAULT), "UTF-8");
            thread.start();
            Class<?> connection = Class.forName("android.app.IUiAutomationConnection");
            Object implementation = Class.forName("android.app.UiAutomationConnection").getDeclaredConstructor().newInstance();
            Constructor<?> ctor = UiAutomation.class.getDeclaredConstructor(Looper.class, connection);
            ctor.setAccessible(true);
            ui = ctor.newInstance(thread.getLooper(), implementation);
            Method connect = UiAutomation.class.getDeclaredMethod("connect");
            connect.setAccessible(true);
            connect.invoke(ui);
            UiAutomation automation = (UiAutomation) ui;
            AccessibilityNodeInfo field = null;
            long deadline = SystemClock.uptimeMillis() + 8000;
            while (field == null && SystemClock.uptimeMillis() < deadline) {
                List<AccessibilityNodeInfo> nodes = new ArrayList<>();
                collect(automation.getRootInActiveWindow(), nodes);
                for (AccessibilityNodeInfo n : nodes) if (n.isFocused()) { field = n; break; }
                if (field == null && nodes.size() == 1) field = nodes.get(0);
                if (field == null) SystemClock.sleep(200);
            }
            if (field == null) throw new IllegalStateException("No unique/focused editable field");
            Bundle value = new Bundle();
            value.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
            if (!field.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, value))
                throw new IllegalStateException("ACTION_SET_TEXT rejected");
            System.out.println("PASS: Unicode text set through accessibility");
            code = 0;
        } catch (Throwable e) {
            e.printStackTrace();
        } finally {
            if (ui != null) try {
                Method disconnect = UiAutomation.class.getDeclaredMethod("disconnect");
                disconnect.setAccessible(true);
                disconnect.invoke(ui);
            } catch (Throwable ignored) { }
            thread.quitSafely();
        }
        System.exit(code);
    }
}
