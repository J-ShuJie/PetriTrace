using PiCameraControl.Manager.Core.Configuration;

namespace PiCameraControl.Manager.Core.Connectivity;

public enum ConnectionKind
{
    LastSuccessful,
    LocalNetwork,
    Mdns,
    Tailscale,
}

public sealed record DeviceEndpoint(Uri BaseUri, ConnectionKind Kind, string Label);

public static class EndpointCatalog
{
    public static (Uri? Local, Uri? Tailscale) AccessLinks(DeviceProfile profile)
    {
        bool IsRemote(string? host)
        {
            if (string.IsNullOrWhiteSpace(host)) return false;
            if (host.Equals(profile.TailscaleAddress, StringComparison.OrdinalIgnoreCase) ||
                host.EndsWith(".ts.net", StringComparison.OrdinalIgnoreCase)) return true;
            if (!System.Net.IPAddress.TryParse(host, out var ip)) return false;
            var bytes = ip.GetAddressBytes();
            return (bytes.Length == 4 && bytes[0] == 100 && bytes[1] >= 64 && bytes[1] <= 127) ||
                (bytes.Length == 16 && bytes[0] == 0xfd && bytes[1] == 0x7a && bytes[2] == 0x11 && bytes[3] == 0x5c);
        }
        Uri? Url(string? host) => HostAddress.IsSafeHost(host)
            ? new UriBuilder(profile.UseHttps ? Uri.UriSchemeHttps : Uri.UriSchemeHttp, host!, profile.WebPort).Uri
            : null;
        var host = profile.HostName;
        if (Uri.CheckHostName(host) is not (UriHostNameType.IPv4 or UriHostNameType.IPv6) &&
            !host.EndsWith(".local", StringComparison.OrdinalIgnoreCase) && !host.Contains('.'))
            host += ".local";
        return ((IsRemote(profile.LocalAddress) ? null : Url(profile.LocalAddress))
            ?? (IsRemote(host) ? null : Url(host)), Url(profile.TailscaleAddress));
    }

    public static IReadOnlyList<DeviceEndpoint> Build(DeviceProfile profile)
    {
        ArgumentNullException.ThrowIfNull(profile);
        var endpoints = new List<DeviceEndpoint>();

        AddAbsolute(endpoints, profile.LastSuccessfulBaseUrl, ConnectionKind.LastSuccessful, "Last successful");

        var ordered = profile.PreferredConnection switch
        {
            PreferredConnection.Tailscale => new[] { ConnectionKind.Tailscale, ConnectionKind.LocalNetwork, ConnectionKind.Mdns },
            PreferredConnection.LocalNetwork => new[] { ConnectionKind.LocalNetwork, ConnectionKind.Mdns, ConnectionKind.Tailscale },
            _ => new[] { ConnectionKind.LocalNetwork, ConnectionKind.Mdns, ConnectionKind.Tailscale },
        };

        foreach (var kind in ordered)
        {
            switch (kind)
            {
                case ConnectionKind.LocalNetwork:
                    AddHost(endpoints, profile, profile.LocalAddress, kind, "Local network");
                    break;
                case ConnectionKind.Mdns:
                    var mdns = Uri.CheckHostName(profile.HostName) is UriHostNameType.IPv4 or UriHostNameType.IPv6 ||
                               profile.HostName.EndsWith(".local", StringComparison.OrdinalIgnoreCase)
                        ? profile.HostName
                        : profile.HostName + ".local";
                    AddHost(endpoints, profile, mdns, kind, "Local network (mDNS)");
                    break;
                case ConnectionKind.Tailscale:
                    AddHost(endpoints, profile, profile.TailscaleAddress, kind, "Tailscale");
                    break;
            }
        }

        return endpoints
            .DistinctBy(endpoint => endpoint.BaseUri.AbsoluteUri, StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static void AddHost(
        ICollection<DeviceEndpoint> endpoints,
        DeviceProfile profile,
        string? host,
        ConnectionKind kind,
        string label)
    {
        if (!HostAddress.IsSafeHost(host))
            return;

        var builder = new UriBuilder(profile.UseHttps ? Uri.UriSchemeHttps : Uri.UriSchemeHttp, host!, profile.WebPort);
        endpoints.Add(new DeviceEndpoint(builder.Uri, kind, label));
    }

    private static void AddAbsolute(
        ICollection<DeviceEndpoint> endpoints,
        string? value,
        ConnectionKind kind,
        string label)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri) ||
            (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps) ||
            !string.IsNullOrEmpty(uri.UserInfo))
            return;

        endpoints.Add(new DeviceEndpoint(
            new UriBuilder(uri) { Path = string.Empty, Query = string.Empty, Fragment = string.Empty }.Uri,
            kind,
            label));
    }
}
