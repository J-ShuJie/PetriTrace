using System.Net;
using System.Text.Json;
using PiCameraControl.Manager.Core.Configuration;

namespace PiCameraControl.Manager.Core.Connectivity;

public sealed record HealthProbeResult(
    DeviceEndpoint Endpoint,
    bool IsHealthy,
    TimeSpan Duration,
    string? Backend = null,
    string? Error = null,
    HttpStatusCode? StatusCode = null);

public sealed record ConnectionResolution(
    DeviceEndpoint? Endpoint,
    IReadOnlyList<HealthProbeResult> Attempts)
{
    public bool IsConnected => Endpoint is not null;
}

public interface IHealthProbe
{
    Task<HealthProbeResult> ProbeAsync(DeviceEndpoint endpoint, CancellationToken cancellationToken = default);
}

public sealed class HttpHealthProbe : IHealthProbe
{
    private readonly HttpClient _client;
    private readonly TimeSpan _timeout;

    public HttpHealthProbe(HttpClient client, TimeSpan? timeout = null)
    {
        _client = client ?? throw new ArgumentNullException(nameof(client));
        _timeout = timeout ?? TimeSpan.FromSeconds(3);
        if (_timeout <= TimeSpan.Zero)
            throw new ArgumentOutOfRangeException(nameof(timeout), "Probe timeout must be positive.");
    }

    public async Task<HealthProbeResult> ProbeAsync(
        DeviceEndpoint endpoint,
        CancellationToken cancellationToken = default)
    {
        var startedAt = System.Diagnostics.Stopwatch.GetTimestamp();
        using var timeoutSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeoutSource.CancelAfter(_timeout);
        try
        {
            var healthUri = new Uri(endpoint.BaseUri, "/health");
            using var response = await _client.GetAsync(
                healthUri, HttpCompletionOption.ResponseHeadersRead, timeoutSource.Token).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
                return Failed(endpoint, startedAt, $"HTTP {(int)response.StatusCode}", response.StatusCode);

            await using var body = await response.Content.ReadAsStreamAsync(timeoutSource.Token).ConfigureAwait(false);
            using var json = await JsonDocument.ParseAsync(body, cancellationToken: timeoutSource.Token).ConfigureAwait(false);
            var root = json.RootElement;
            var ok = root.TryGetProperty("ok", out var okValue) && okValue.ValueKind == JsonValueKind.True;
            var backend = root.TryGetProperty("backend", out var backendValue) ? backendValue.GetString() : null;
            return ok
                ? new HealthProbeResult(endpoint, true, System.Diagnostics.Stopwatch.GetElapsedTime(startedAt), backend, StatusCode: response.StatusCode)
                : Failed(endpoint, startedAt, "Health response did not report ok=true.", response.StatusCode);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return Failed(endpoint, startedAt, "Connection timed out.");
        }
        catch (Exception exception) when (exception is HttpRequestException or JsonException or IOException)
        {
            return Failed(endpoint, startedAt, exception.Message);
        }
    }

    private static HealthProbeResult Failed(
        DeviceEndpoint endpoint,
        long startedAt,
        string error,
        HttpStatusCode? statusCode = null) =>
        new(endpoint, false, System.Diagnostics.Stopwatch.GetElapsedTime(startedAt), Error: error, StatusCode: statusCode);
}

public sealed class ConnectionResolver
{
    private readonly IHealthProbe _healthProbe;

    public ConnectionResolver(IHealthProbe healthProbe)
    {
        _healthProbe = healthProbe ?? throw new ArgumentNullException(nameof(healthProbe));
    }

    public async Task<ConnectionResolution> ResolveAsync(
        DeviceProfile profile,
        CancellationToken cancellationToken = default)
    {
        var attempts = new List<HealthProbeResult>();
        foreach (var endpoint in EndpointCatalog.Build(profile))
        {
            cancellationToken.ThrowIfCancellationRequested();
            var result = await _healthProbe.ProbeAsync(endpoint, cancellationToken).ConfigureAwait(false);
            attempts.Add(result);
            if (result.IsHealthy)
                return new ConnectionResolution(endpoint, attempts);
        }

        return new ConnectionResolution(null, attempts);
    }
}
