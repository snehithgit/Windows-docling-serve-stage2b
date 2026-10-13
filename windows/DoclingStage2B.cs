using System;
using System.Diagnostics;
using System.Drawing;
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

        string data = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DoclingStage2B");
        Directory.CreateDirectory(data);
        string statusPath = Path.Combine(data, "startup.status");
        if (File.Exists(statusPath)) File.Delete(statusPath);

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
                Form splash = new Form();
                splash.Text = "Docling Stage-2B · Offline";
                splash.StartPosition = FormStartPosition.CenterScreen;
                splash.ClientSize = new Size(490, 156);
                splash.FormBorderStyle = FormBorderStyle.FixedSingle;
                splash.MaximizeBox = false;
                splash.BackColor = Color.FromArgb(18, 32, 55);
                splash.ForeColor = Color.White;

                Label header = new Label();
                header.Text = "Docling Stage-2B";
                header.Font = new Font("Segoe UI", 21, FontStyle.Bold);
                header.ForeColor = Color.White;
                header.AutoSize = true;
                header.Location = new Point(24, 23);
                splash.Controls.Add(header);

                Label status = new Label();
                status.Text = "Initializing bundled offline services...";
                status.Font = new Font("Segoe UI", 10);
                status.ForeColor = Color.FromArgb(180, 200, 230);
                status.AutoSize = false;
                status.Size = new Size(440, 60);
                status.Location = new Point(26, 91);
                splash.Controls.Add(status);

                bool ready = false;
                bool terminated = false;
                Timer timer = new Timer();
                timer.Interval = 450;
                timer.Tick += delegate(object sender, EventArgs e) {
                    try {
                        if (File.Exists(statusPath)) {
                            string message = File.ReadAllText(statusPath).Trim();
                            if (message == "READY") {
                                ready = true;
                                timer.Stop();
                                splash.Close();
                                return;
                            }
                            if (message.Length > 0) status.Text = message;
                        }
                    } catch (IOException) { }
                    if (child.HasExited) {
                        terminated = true;
                        timer.Stop();
                        splash.Close();
                    }
                };
                splash.FormClosing += delegate(object sender, FormClosingEventArgs e) {
                    timer.Stop();
                    if (!ready && !child.HasExited && !terminated) {
                        child.Kill();
                    }
                };
                timer.Start();
                Application.EnableVisualStyles();
                Application.Run(splash);
                timer.Dispose();
                splash.Dispose();

                if (terminated && child.ExitCode != 0) {
                    MessageBox.Show("Offline services could not start. Check logs at:\n" +
                                    Path.Combine(data, "logs"),
                                    "Docling Stage-2B", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch (Exception e)
        {
            MessageBox.Show(e.Message, "Docling Stage-2B",
                            MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
