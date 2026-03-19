using System.Diagnostics;
using System.IO.Compression;
using System.Reflection;
using System.Text;

namespace HandGalaxySetup;

internal static class Program
{
    private const string AppName = "Hand Galaxy TouchDesigner";
    private const string AppVersion = "1.0.0";
    private const string PythonEmbedUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip";
    private const string GetPipUrl = "https://bootstrap.pypa.io/get-pip.py";
    private const string ModelUrl = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";

    [STAThread]
    private static async Task<int> Main(string[] args)
    {
        var noLaunch = args.Any(arg => string.Equals(arg, "--no-launch", StringComparison.OrdinalIgnoreCase));
        var installRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "HandGalaxyTouchDesigner"
        );
        var appRoot = Path.Combine(installRoot, "app");
        var runtimeRoot = Path.Combine(installRoot, "runtime");
        var pythonRoot = Path.Combine(runtimeRoot, "python");
        var modelsRoot = Path.Combine(installRoot, "models");
        var launchersRoot = Path.Combine(installRoot, "launchers");
        var quickStartPath = Path.Combine(installRoot, "Hand Galaxy Quick Start.txt");
        var versionFilePath = Path.Combine(installRoot, "VERSION.txt");
        var desktopRoot = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        var startMenuRoot = Environment.GetFolderPath(Environment.SpecialFolder.Programs);
        var startMenuFolder = Path.Combine(startMenuRoot, AppName);
        var sameVersionInstalled = File.Exists(versionFilePath) &&
            string.Equals(File.ReadAllText(versionFilePath).Trim(), AppVersion, StringComparison.OrdinalIgnoreCase);

        try
        {
            Console.OutputEncoding = Encoding.UTF8;
            Banner();
            Directory.CreateDirectory(installRoot);
            Directory.CreateDirectory(runtimeRoot);
            Directory.CreateDirectory(modelsRoot);
            Directory.CreateDirectory(launchersRoot);
            Directory.CreateDirectory(startMenuFolder);

            Console.WriteLine($"Installing to: {installRoot}");
            ExtractPayload(appRoot);
            await EnsureEmbeddedPythonAsync(pythonRoot);
            if (NeedsPackageInstall(pythonRoot) || !sameVersionInstalled)
            {
                await EnsurePipAsync(pythonRoot);
                await InstallRequirementsAsync(pythonRoot, appRoot);
            }
            else
            {
                Console.WriteLine($"Version {AppVersion} is already installed. Reusing existing Python packages.");
            }
            await EnsureModelAsync(modelsRoot);
            WriteQuickStartGuide(quickStartPath, installRoot);
            WriteLaunchers(launchersRoot, appRoot, pythonRoot, quickStartPath);
            PublishDesktopArtifacts(launchersRoot, quickStartPath, desktopRoot);
            PublishStartMenuArtifacts(launchersRoot, quickStartPath, startMenuFolder);
            File.WriteAllText(versionFilePath, AppVersion + Environment.NewLine, Encoding.UTF8);

            Console.WriteLine();
            Console.WriteLine($"Install complete. {AppName} v{AppVersion} is ready.");
            Console.WriteLine("Desktop items created:");
            Console.WriteLine("  Hand Galaxy");
            Console.WriteLine("  Hand Galaxy Quick Start");
            Console.WriteLine("Start Menu folder created:");
            Console.WriteLine($"  {startMenuFolder}");

            if (!noLaunch)
            {
                var launcher = Path.Combine(launchersRoot, "Hand Galaxy.cmd");
                Console.WriteLine();
                Console.WriteLine("Launching Hand Galaxy...");
                Process.Start(new ProcessStartInfo
                {
                    FileName = launcher,
                    WorkingDirectory = launchersRoot,
                    UseShellExecute = true
                });
            }
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine();
            Console.Error.WriteLine("SETUP FAILED");
            Console.Error.WriteLine(ex.Message);
            Console.Error.WriteLine(ex.StackTrace);
            Console.Error.WriteLine();
            Console.Error.WriteLine("Press Enter to close.");
            Console.ReadLine();
            return 1;
        }
    }

    private static void Banner()
    {
        Console.WriteLine("========================================");
        Console.WriteLine($" {AppName.ToUpperInvariant()} // SETUP v{AppVersion}");
        Console.WriteLine("========================================");
        Console.WriteLine();
    }

    private static bool NeedsPackageInstall(string pythonRoot)
    {
        var mediapipeInit = Path.Combine(pythonRoot, "Lib", "site-packages", "mediapipe", "__init__.py");
        var oscInit = Path.Combine(pythonRoot, "Lib", "site-packages", "pythonosc", "__init__.py");
        var cv2Path = Path.Combine(pythonRoot, "Lib", "site-packages", "cv2");
        return !(File.Exists(mediapipeInit) && File.Exists(oscInit) && Directory.Exists(cv2Path));
    }

    private static void ExtractPayload(string appRoot)
    {
        Console.WriteLine("Extracting app payload...");
        if (Directory.Exists(appRoot))
        {
            Directory.Delete(appRoot, recursive: true);
        }

        Directory.CreateDirectory(appRoot);

        using var resource = Assembly.GetExecutingAssembly()
            .GetManifestResourceStream("HandGalaxy.Payload.zip")
            ?? throw new InvalidOperationException("Embedded payload was not found.");
        var tempZip = Path.Combine(Path.GetTempPath(), $"hand-galaxy-payload-{Guid.NewGuid():N}.zip");
        using (var tempStream = File.Create(tempZip))
        {
            resource.CopyTo(tempStream);
        }

        ZipFile.ExtractToDirectory(tempZip, appRoot, overwriteFiles: true);
        File.Delete(tempZip);
    }

    private static async Task EnsureEmbeddedPythonAsync(string pythonRoot)
    {
        var pythonExe = Path.Combine(pythonRoot, "python.exe");
        if (!File.Exists(pythonExe))
        {
            Console.WriteLine("Downloading embedded Python...");
            Directory.CreateDirectory(pythonRoot);
            var zipPath = Path.Combine(Path.GetTempPath(), $"python-embed-{Guid.NewGuid():N}.zip");
            using var client = new HttpClient();
            await using (var netStream = await client.GetStreamAsync(PythonEmbedUrl))
            await using (var fileStream = File.Create(zipPath))
            {
                await netStream.CopyToAsync(fileStream);
            }

            ZipFile.ExtractToDirectory(zipPath, pythonRoot, overwriteFiles: true);
            File.Delete(zipPath);
        }

        PatchPthFile(pythonRoot);
    }

    private static void PatchPthFile(string pythonRoot)
    {
        var pthFile = Directory.EnumerateFiles(pythonRoot, "python*._pth").FirstOrDefault();
        if (pthFile is null)
        {
            throw new FileNotFoundException("Could not find the embedded Python ._pth file.");
        }

        var lines = new[]
        {
            Path.GetFileNameWithoutExtension(pthFile).Replace("._pth", "") + ".zip",
            ".",
            "Lib",
            "Lib\\site-packages",
            "import site"
        };
        File.WriteAllLines(pthFile, lines);
    }

    private static async Task EnsurePipAsync(string pythonRoot)
    {
        var pythonExe = Path.Combine(pythonRoot, "python.exe");
        var getPipPath = Path.Combine(pythonRoot, "get-pip.py");
        if (!File.Exists(getPipPath))
        {
            Console.WriteLine("Downloading pip bootstrap...");
            using var client = new HttpClient();
            await using var netStream = await client.GetStreamAsync(GetPipUrl);
            await using var fileStream = File.Create(getPipPath);
            await netStream.CopyToAsync(fileStream);
        }

        Console.WriteLine("Bootstrapping pip...");
        RunProcess(
            pythonExe,
            $"\"{getPipPath}\" --disable-pip-version-check --no-warn-script-location",
            pythonRoot
        );
    }

    private static async Task InstallRequirementsAsync(string pythonRoot, string appRoot)
    {
        var pythonExe = Path.Combine(pythonRoot, "python.exe");
        var baseRequirements = Path.Combine(appRoot, "requirements.txt");
        var virtualCamRequirements = Path.Combine(appRoot, "requirements-virtualcam.txt");

        Console.WriteLine("Installing Python packages...");
        RunProcess(
            pythonExe,
            $"-m pip install --upgrade pip",
            appRoot
        );
        RunProcess(
            pythonExe,
            $"-m pip install -r \"{baseRequirements}\"",
            appRoot
        );

        if (File.Exists(virtualCamRequirements))
        {
            RunProcess(
                pythonExe,
                $"-m pip install -r \"{virtualCamRequirements}\"",
                appRoot
            );
        }

        await Task.CompletedTask;
    }

    private static async Task EnsureModelAsync(string modelsRoot)
    {
        var modelPath = Path.Combine(modelsRoot, "hand_landmarker.task");
        if (File.Exists(modelPath))
        {
            return;
        }

        Console.WriteLine("Downloading MediaPipe hand model...");
        using var client = new HttpClient();
        await using var netStream = await client.GetStreamAsync(ModelUrl);
        await using var fileStream = File.Create(modelPath);
        await netStream.CopyToAsync(fileStream);
    }

    private static void WriteLaunchers(string launchersRoot, string appRoot, string pythonRoot, string quickStartPath)
    {
        var pythonExe = Path.Combine(pythonRoot, "python.exe");
        var srcRoot = Path.Combine(appRoot, "src");
        var modelPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "HandGalaxyTouchDesigner",
            "models",
            "hand_landmarker.task"
        );

        Directory.CreateDirectory(launchersRoot);

        var commandPrefix = $@"""{pythonExe}"" -c ""import sys; sys.path.insert(0, r'{srcRoot}'); from hand_galaxy.main import main; main()"" --model-path ""{modelPath}"" --osc-host 127.0.0.1 --osc-port 7000";

        var previewLauncher = $"""
@echo off
setlocal
title Hand Galaxy - Camera Preview
{commandPrefix} %*
if errorlevel 1 (
  echo.
  echo Hand Galaxy closed with an error.
  pause
)
endlocal
""";

        var virtualLauncher = $"""
@echo off
setlocal
title Hand Galaxy - TouchDesigner Mode
{commandPrefix} --virtual-cam %*
if errorlevel 1 (
  echo.
  echo Hand Galaxy closed with an error.
  pause
)
endlocal
""";

        var guideLauncher = $"""
@echo off
start "" "{quickStartPath}"
""";

        var menuLauncher = $"""
@echo off
setlocal
title Hand Galaxy
cls
echo ========================================
echo   HAND GALAXY TOUCHDESIGNER
echo ========================================
echo.
echo   [1] Run Camera Preview
echo   [2] Run TouchDesigner Mode (requires OBS Virtual Camera or UnityCapture)
echo   [3] Open Quick Start Guide
echo   [Q] Quit
echo.
echo   Best first run: press 1.
echo.
choice /c 123Q /n /m "Choose an option: "
if errorlevel 4 goto :done
if errorlevel 3 start "" "{quickStartPath}" & goto :done
if errorlevel 2 call "{Path.Combine(launchersRoot, "Hand Galaxy TouchDesigner Mode.cmd")}" & goto :done
call "{Path.Combine(launchersRoot, "Hand Galaxy Camera Preview.cmd")}"
:done
endlocal
""";

        File.WriteAllText(Path.Combine(launchersRoot, "Hand Galaxy.cmd"), menuLauncher, Encoding.ASCII);
        File.WriteAllText(Path.Combine(launchersRoot, "Hand Galaxy Camera Preview.cmd"), previewLauncher, Encoding.ASCII);
        File.WriteAllText(Path.Combine(launchersRoot, "Hand Galaxy TouchDesigner Mode.cmd"), virtualLauncher, Encoding.ASCII);
        File.WriteAllText(Path.Combine(launchersRoot, "Open Hand Galaxy Guide.cmd"), guideLauncher, Encoding.ASCII);
    }

    private static void WriteQuickStartGuide(string quickStartPath, string installRoot)
    {
        var lines = new[]
        {
            "HAND GALAXY TOUCHDESIGNER // QUICK START",
            "",
            "1. Double-click 'Hand Galaxy' on your Desktop.",
            "2. Press 1 for the normal camera preview mode. This is the best first run.",
            "3. Press 2 only if you already installed OBS Virtual Camera or UnityCapture.",
            "4. In TouchDesigner, listen for OSC on UDP port 7000.",
            "5. If virtual-camera mode is available, point Video Device In TOP at the virtual camera.",
            "",
            "Installed files:",
            $"  {installRoot}",
            "",
            "TouchDesigner setup docs:",
            $"  {Path.Combine(installRoot, "app", "touchdesigner", "NETWORK_SETUP.md")}",
            "",
            "TouchDesigner mode note:",
            "  The installer includes pyvirtualcam, but Windows still needs a virtual-camera backend.",
            "  OBS Virtual Camera and UnityCapture are the easiest options.",
            "",
            "If the program exits with an error, relaunch from the desktop shortcut and read the console window.",
        };
        File.WriteAllLines(quickStartPath, lines, Encoding.UTF8);
    }

    private static void PublishDesktopArtifacts(string launchersRoot, string quickStartPath, string desktopRoot)
    {
        RemoveLegacyArtifacts(desktopRoot);
        CreateShortcutOrCopy(
            Path.Combine(launchersRoot, "Hand Galaxy.cmd"),
            Path.Combine(desktopRoot, "Hand Galaxy.lnk"),
            "Launch Hand Galaxy"
        );
        CreateShortcutOrCopy(
            quickStartPath,
            Path.Combine(desktopRoot, "Hand Galaxy Quick Start.lnk"),
            "Open the Hand Galaxy quick start guide"
        );
    }

    private static void PublishStartMenuArtifacts(string launchersRoot, string quickStartPath, string startMenuFolder)
    {
        Directory.CreateDirectory(startMenuFolder);
        RemoveLegacyArtifacts(startMenuFolder);
        CreateShortcutOrCopy(
            Path.Combine(launchersRoot, "Hand Galaxy.cmd"),
            Path.Combine(startMenuFolder, "Hand Galaxy.lnk"),
            "Launch Hand Galaxy"
        );
        CreateShortcutOrCopy(
            Path.Combine(launchersRoot, "Hand Galaxy Camera Preview.cmd"),
            Path.Combine(startMenuFolder, "Hand Galaxy Camera Preview.lnk"),
            "Launch Hand Galaxy in camera preview mode"
        );
        CreateShortcutOrCopy(
            Path.Combine(launchersRoot, "Hand Galaxy TouchDesigner Mode.cmd"),
            Path.Combine(startMenuFolder, "Hand Galaxy TouchDesigner Mode.lnk"),
            "Launch Hand Galaxy in TouchDesigner mode"
        );
        CreateShortcutOrCopy(
            quickStartPath,
            Path.Combine(startMenuFolder, "Hand Galaxy Quick Start.lnk"),
            "Open the Hand Galaxy quick start guide"
        );
    }

    private static void CopyFile(string source, string destination)
    {
        File.Copy(source, destination, overwrite: true);
    }

    private static void RemoveLegacyArtifacts(string root)
    {
        var names = new[]
        {
            "Hand Galaxy.cmd",
            "Hand Galaxy Camera Preview.cmd",
            "Hand Galaxy TouchDesigner Mode.cmd",
            "Hand Galaxy Tracker.cmd",
            "Hand Galaxy Tracker (Virtual Cam).cmd",
            "Open Hand Galaxy Guide.cmd",
            "Hand Galaxy Quick Start.txt",
            "Hand Galaxy.lnk",
            "Hand Galaxy Camera Preview.lnk",
            "Hand Galaxy TouchDesigner Mode.lnk",
            "Open Hand Galaxy Guide.lnk",
            "Hand Galaxy Quick Start.lnk"
        };

        foreach (var name in names)
        {
            var path = Path.Combine(root, name);
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
    }

    private static void CreateShortcutOrCopy(string targetPath, string shortcutPath, string description)
    {
        try
        {
            if (File.Exists(shortcutPath))
            {
                File.Delete(shortcutPath);
            }

            var shellType = Type.GetTypeFromProgID("WScript.Shell")
                ?? throw new InvalidOperationException("WScript.Shell is unavailable.");
            var shell = Activator.CreateInstance(shellType)
                ?? throw new InvalidOperationException("Could not create WScript.Shell.");
            var shortcut = shellType.InvokeMember(
                "CreateShortcut",
                BindingFlags.InvokeMethod,
                binder: null,
                target: shell,
                args: new object[] { shortcutPath }
            );

            if (shortcut is null)
            {
                throw new InvalidOperationException("Could not create shortcut object.");
            }

            var shortcutType = shortcut.GetType();
            shortcutType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
            shortcutType.InvokeMember(
                "WorkingDirectory",
                BindingFlags.SetProperty,
                null,
                shortcut,
                new object[] { Path.GetDirectoryName(targetPath) ?? string.Empty }
            );
            shortcutType.InvokeMember("Description", BindingFlags.SetProperty, null, shortcut, new object[] { description });
            shortcutType.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, Array.Empty<object>());
        }
        catch
        {
            var fallbackPath = Path.Combine(Path.GetDirectoryName(shortcutPath)!, Path.GetFileName(targetPath));
            CopyFile(targetPath, fallbackPath);
        }
    }

    private static void RunProcess(string fileName, string arguments, string workingDirectory)
    {
        var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
                WorkingDirectory = workingDirectory,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            }
        };

        process.OutputDataReceived += (_, eventArgs) =>
        {
            if (!string.IsNullOrWhiteSpace(eventArgs.Data))
            {
                Console.WriteLine(eventArgs.Data);
            }
        };
        process.ErrorDataReceived += (_, eventArgs) =>
        {
            if (!string.IsNullOrWhiteSpace(eventArgs.Data))
            {
                Console.Error.WriteLine(eventArgs.Data);
            }
        };

        if (!process.Start())
        {
            throw new InvalidOperationException($"Failed to start process: {fileName}");
        }

        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        process.WaitForExit();

        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(
                $"Process failed with exit code {process.ExitCode}: {fileName} {arguments}"
            );
        }
    }
}
