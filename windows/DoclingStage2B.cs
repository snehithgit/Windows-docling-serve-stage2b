using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class DoclingStage2B
{
    [STAThread]
    private static int Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string python = Path.Combine(root, "runtime", "pythonw.exe");
        string script = Path.Combine(root, "windows", "launcher.py");
        if (!File.Exists(python) || !File.Exists(script))
        {
            MessageBox.Show("The offline runtime is missing. Please reinstall Docling Stage-2B.",
                            "Docling Stage-2B", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        try
        {
            using (Process child = Process.Start(new ProcessStartInfo {
                FileName = python,
                Arguments = "\"" + script + "\"",
                WorkingDirectory = root,
                UseShellExecute = false,
                CreateNoWindow = true
            }))
            {
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch (Exception e)
        {
            MessageBox.Show(e.Message, "Docling Stage-2B", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
