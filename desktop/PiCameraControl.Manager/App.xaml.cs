using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Windows;
using PiCameraControl.Manager.Core.Protocol;

namespace PiCameraControl.Manager;

public partial class App : Application
{
    private const string InstanceName = "PiCameraControl.Manager.v1";
    private Mutex? _instanceMutex;
    private CancellationTokenSource? _activationCancellation;

    public App()
    {
        // WPF's font cache expects WINDIR to be present. Some managed launchers
        // intentionally start applications with a reduced environment.
        if (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("WINDIR")))
            Environment.SetEnvironmentVariable(
                "WINDIR",
                Environment.GetFolderPath(Environment.SpecialFolder.Windows));
    }

    protected override async void OnStartup(StartupEventArgs e)
    {
        _instanceMutex = new Mutex(initiallyOwned: true, InstanceName, out var isPrimaryInstance);
        if (!isPrimaryInstance)
        {
            var protocolArgument = e.Args.FirstOrDefault(value =>
                value.StartsWith("picameracontrol:", StringComparison.OrdinalIgnoreCase));
            await ForwardActivationAsync(protocolArgument ?? string.Empty);
            Shutdown();
            return;
        }

        base.OnStartup(e);
        _activationCancellation = new CancellationTokenSource();
        var window = new MainWindow();
        MainWindow = window;
        window.Show();
        _ = ListenForActivationsAsync(_activationCancellation.Token);
    }

    private async Task ListenForActivationsAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                await using var pipe = new NamedPipeServerStream(
                    InstanceName,
                    PipeDirection.In,
                    1,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly);
                await pipe.WaitForConnectionAsync(cancellationToken);
                using var reader = new StreamReader(pipe, Encoding.UTF8, detectEncodingFromByteOrderMarks: false,
                    bufferSize: 1024, leaveOpen: true);
                var activation = await reader.ReadLineAsync(cancellationToken) ?? string.Empty;
                if (activation.Length > 4096)
                    continue;
                await Dispatcher.InvokeAsync(() => HandleActivationAsync(activation)).Task.Unwrap();
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                break;
            }
            catch
            {
                await Task.Delay(150, cancellationToken);
            }
        }
    }

    private async Task HandleActivationAsync(string activation)
    {
        if (MainWindow is not MainWindow window)
            return;

        if (!window.IsVisible)
            window.Show();
        if (window.WindowState == WindowState.Minimized)
            window.WindowState = WindowState.Normal;
        window.Activate();

        if (ManagerProtocolParser.TryParse(activation, out var request) && request is not null)
            await window.HandleProtocolActivationAsync(request);
    }

    private static async Task ForwardActivationAsync(string activation)
    {
        try
        {
            await using var pipe = new NamedPipeClientStream(
                ".", InstanceName, PipeDirection.Out, PipeOptions.Asynchronous);
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(4));
            await pipe.ConnectAsync(timeout.Token);
            await using var writer = new StreamWriter(pipe, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false),
                bufferSize: 1024, leaveOpen: true) { AutoFlush = true };
            await writer.WriteLineAsync(activation.AsMemory(), timeout.Token);
        }
        catch
        {
            // The primary instance may be closing. The secondary must still exit
            // instead of creating a competing manager window.
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _activationCancellation?.Cancel();
        _activationCancellation?.Dispose();
        try
        {
            _instanceMutex?.ReleaseMutex();
        }
        catch (ApplicationException)
        {
            // This process never owned the mutex (secondary instance).
        }
        _instanceMutex?.Dispose();
        base.OnExit(e);
    }
}
