using System.Diagnostics;
using System.IO.Compression;
using System.Reflection;
using System.Text;

namespace HandGalaxySetup;

internal static class Program
{
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
        var desktopRoot = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);

        try
        {
            Console.OutputEncoding = Encoding.UTF8;
            Banner();
            Directory.CreateDirectory(installRoot);
            Directory.CreateDirectory(runtimeRoot);
            Directory.CreateDirectory(modelsRoot);
            Directory.CreateDirectory(launchersRoot);

            Console.WriteLine($"Installing to: {installRoot}");
            ExtractPayload(appRoot);
            await EnsureEmbeddedPythonAsync(pythonRoot);
            await EnsurePipAsync(pythonRoot);
            await InstallRequirementsAsync(pythonRoot, appRoot);
            await EnsureModelAsync(modelsRoot);
            WriteLaunchers(launchersRoot, appRoot, pythonRoot);
            CopyDesktopLaunchers(launchersRoot, desktopRoot);

            Console.WriteLine();
            Console.WriteLine("Install complete.");
            Console.WriteLine("Desktop launchers created:");
            Console.WriteLine("  Hand Galaxy Tracker.cmd");
            Console.WriteLine("  Hand Galaxy Tracker (Virtual Cam).cmd");

            if (!noLaunch)
            {
                var launcher = Path.Combine(launchersRoot, "Hand Galaxy Tracker.cmd");
                Console.WriteLine();
                Console.WriteLine("Launching tracker...");
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
        Console.WriteLine(" HAND GALAXY TOUCHDESIGNER // SETUP");
        Console.WriteLine("========================================");
        Console.WriteLine();
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

    private static void WriteLaunchers(string launchersRoot, string appRoot, string pythonRoot)
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

        var baseLauncher = $"""
@echo off
setlocal
"{pythonExe}" -c "import sys; sys.path.insert(0, r'{srcRoot}'); from hand_galaxy.main import main; main()" --model-path "{modelPath}" --osc-host 127.0.0.1 --osc-port 7000 %*
endlocal
""";

        var virtualLauncher = $"""
@echo off
setlocal
"{pythonExe}" -c "import sys; sys.path.insert(0, r'{srcRoot}'); from hand_galaxy.main import main; main()" --model-path "{modelPath}" --osc-host 127.0.0.1 --osc-port 7000 --virtual-cam %*
endlocal
""";

        File.WriteAllText(Path.Combine(launchersRoot, "Hand Galaxy Tracker.cmd"), baseLauncher);
        File.WriteAllText(Path.Combine(launchersRoot, "Hand Galaxy Tracker (Virtual Cam).cmd"), virtualLauncher);
    }

    private static void CopyDesktopLaunchers(string launchersRoot, string desktopRoot)
    {
        File.Copy(
            Path.Combine(launchersRoot, "Hand Galaxy Tracker.cmd"),
            Path.Combine(desktopRoot, "Hand Galaxy Tracker.cmd"),
            overwrite: true
        );
        File.Copy(
            Path.Combine(launchersRoot, "Hand Galaxy Tracker (Virtual Cam).cmd"),
            Path.Combine(desktopRoot, "Hand Galaxy Tracker (Virtual Cam).cmd"),
            overwrite: true
        );
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
