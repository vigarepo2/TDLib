using System.Runtime.InteropServices;

// .NET's built-in P/Invoke calls the C JSON ABI; no third-party package is needed.
internal static class Program
{
    [DllImport("tdjson", CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr td_execute([MarshalAs(UnmanagedType.LPUTF8Str)] string request);

    private static void Main()
    {
        IntPtr result = td_execute("{\"@type\":\"getOption\",\"name\":\"version\"}");
        if (result == IntPtr.Zero) throw new InvalidOperationException("TDLib did not return a synchronous response");
        // TDLib owns the returned memory; copy it before another execute call.
        Console.WriteLine(Marshal.PtrToStringUTF8(result));
    }
}
