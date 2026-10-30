import android.app.UiAutomation;
import android.os.Bundle;
import android.os.HandlerThread;
import android.os.Looper;
import android.os.SystemClock;
import android.graphics.Rect;
import android.util.Base64;
import android.util.Xml;
import android.view.accessibility.AccessibilityNodeInfo;
import java.io.FileOutputStream;
import org.xmlpull.v1.XmlSerializer;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/* One-shot shell helper: set Unicode text through the focused editable node.
 * It performs no clicks and installs no app, IME or accessibility service. */
public class MapUiText {
    private static String string(CharSequence value) { return value == null ? "" : value.toString(); }
    private static void dumpNode(XmlSerializer xml, AccessibilityNodeInfo node) throws Exception {
        if (node == null || !node.isVisibleToUser()) return;
        Rect r = new Rect(); node.getBoundsInScreen(r);
        xml.startTag(null, "node");
        xml.attribute(null, "text", string(node.getText()));
        xml.attribute(null, "content-desc", string(node.getContentDescription()));
        xml.attribute(null, "resource-id", string(node.getViewIdResourceName()));
        xml.attribute(null, "class", string(node.getClassName()));
        xml.attribute(null, "package", string(node.getPackageName()));
        xml.attribute(null, "clickable", String.valueOf(node.isClickable()));
        xml.attribute(null, "scrollable", String.valueOf(node.isScrollable()));
        xml.attribute(null, "editable", String.valueOf(node.isEditable()));
        xml.attribute(null, "enabled", String.valueOf(node.isEnabled()));
        xml.attribute(null, "bounds", "["+r.left+","+r.top+"]["+r.right+","+r.bottom+"]");
        for (int i=0; i<node.getChildCount(); ++i) dumpNode(xml,node.getChild(i));
        xml.endTag(null,"node");
    }

    private static boolean scroll(AccessibilityNodeInfo node) {
        if (node == null || !node.isVisibleToUser()) return false;
        for (int i=0;i<node.getChildCount();++i) if (scroll(node.getChild(i))) return true;
        return node.isScrollable() && node.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD);
    }
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
            if (args.length < 1) throw new IllegalArgumentException("Expected base64 text, --dump PATH or --scroll");
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
            AccessibilityNodeInfo root = null;
            long rootDeadline = SystemClock.uptimeMillis() + 8000;
            while (root == null && SystemClock.uptimeMillis() < rootDeadline) {
                root = automation.getRootInActiveWindow();
                if (root == null) SystemClock.sleep(200);
            }
            if (root == null) throw new IllegalStateException("No active accessibility root");
            if (args[0].equals("--dump")) {
                if (args.length != 2 || !args[1].equals("/data/local/tmp/map-auto-ui.xml"))
                    throw new IllegalArgumentException("Unsupported dump destination");
                try (FileOutputStream out = new FileOutputStream(args[1])) {
                    XmlSerializer xml=Xml.newSerializer(); xml.setOutput(out,"UTF-8");
                    xml.startDocument("UTF-8",true); xml.startTag(null,"hierarchy");
                    dumpNode(xml,root); xml.endTag(null,"hierarchy"); xml.endDocument();
                }
                System.out.println("PASS: UI hierarchy captured without waiting for map animations");
            } else if (args[0].equals("--scroll")) {
                if (!scroll(root)) throw new IllegalStateException("No scrollable result container advanced");
                System.out.println("PASS: accessibility scroll forward");
            } else {
            String text = new String(Base64.decode(args[0], Base64.DEFAULT), "UTF-8");
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
            }
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
