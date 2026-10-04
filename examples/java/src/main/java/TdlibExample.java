import com.sun.jna.Library;
import com.sun.jna.Native;

/** An offline JSON query. JNA supplies the JNI adapter; this is not TDLib's typed Java API. */
public final class TdlibExample {
    public interface TdJson extends Library {
        String td_execute(String request);
    }

    public static void main(String[] args) {
        String path = System.getenv().getOrDefault("TDLIB_LIBRARY_PATH", "tdjson");
        TdJson tdlib = Native.load(path, TdJson.class);
        String result = tdlib.td_execute("{\"@type\":\"getOption\",\"name\":\"version\"}");
        if (result == null) throw new IllegalStateException("TDLib did not return a synchronous response");
        System.out.println(result);
    }
}
