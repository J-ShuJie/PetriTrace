using System.Buffers;
using System.Security.Cryptography;
using System.Text;

namespace PiCameraControl.Manager.Core.Deployment;

/// <summary>
/// Writes one secret line to a remote command's standard input without placing the value in
/// the command text, arguments, environment, result, or logs. The destination is always closed
/// to signal EOF; SSH.NET 2026 requires that for streams returned by SshCommand.CreateInputStream.
/// </summary>
public static class SensitiveCommandInput
{
    public static async Task WriteUtf8LineAndCloseAsync(
        Stream destination,
        ReadOnlyMemory<char> secret,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(destination);
        byte[]? buffer = null;
        try
        {
            ValidateSecret(secret.Span);
            var maximumByteCount = Encoding.UTF8.GetMaxByteCount(secret.Length) + 1;
            buffer = ArrayPool<byte>.Shared.Rent(maximumByteCount);
            var byteCount = Encoding.UTF8.GetBytes(secret.Span, buffer.AsSpan());
            buffer[byteCount++] = (byte)'\n';
            await destination.WriteAsync(buffer.AsMemory(0, byteCount), cancellationToken).ConfigureAwait(false);
            await destination.FlushAsync(cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            if (buffer is not null)
            {
                CryptographicOperations.ZeroMemory(buffer);
                ArrayPool<byte>.Shared.Return(buffer);
            }
            await destination.DisposeAsync().ConfigureAwait(false);
        }
    }

    private static void ValidateSecret(ReadOnlySpan<char> secret)
    {
        if (secret.IsEmpty)
            throw new ArgumentException("The secret cannot be empty.", nameof(secret));
        if (secret.IndexOfAny('\r', '\n', '\0') >= 0)
            throw new ArgumentException("Line-based command input cannot contain CR, LF, or NUL.", nameof(secret));
    }
}
