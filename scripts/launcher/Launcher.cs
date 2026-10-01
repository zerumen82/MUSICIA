// Musicia Launcher — ejecuta scripts\open_musicia.ps1 de forma invisible al doble clic.
//
// Compilación (sin instalar nada, usa el csc.exe que trae Windows):
//   C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:winexe /out:..\..\Musicia.exe /r:System.Windows.Forms.dll Launcher.cs
//
// Este archivo fuente ES la documentación: el EXE nunca se commitea.
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class Launcher
{
    [STAThread]
    static int Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string script = Path.Combine(root, "scripts", "open_musicia.ps1");

        if (!File.Exists(script))
        {
            MessageBox.Show(
                "No se encontró scripts\\open_musicia.ps1 junto al ejecutable.",
                "Musicia", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        string winDir = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        string ps = Path.Combine(winDir, "System32", "WindowsPowerShell", "v1.0", "powershell.exe");

        var psi = new ProcessStartInfo
        {
            FileName = ps,
            Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + script + "\"",
            WorkingDirectory = root,
            UseShellExecute = true,
            WindowStyle = ProcessWindowStyle.Hidden
        };

        try
        {
            Process.Start(psi);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "No se pudo arrancar Musicia:\n" + ex.Message + "\n\nScript: " + script,
                "Musicia", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
