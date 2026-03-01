#!/usr/bin/env python3
"""
Simple HTTPS server to host the YouTube player HTML file.
This allows the player to have a proper origin and send Referer headers to YouTube.

Usage:
    python3 serve_player.py [--port PORT] [--host HOST]

Default:
    Host: 0.0.0.0 (all interfaces)
    Port: 8443

The server will be available at: https://localhost:8443/player.html

For production, use a proper web server like nginx or Apache with:
- Valid SSL certificate (Let's Encrypt)
- CORS headers configured
"""

import argparse
import http.server
import os
import ssl
import socket
import sys
from pathlib import Path


class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with CORS headers."""

    def __init__(self, *args, directory=None, **kwargs):
        self.directory = directory
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        # Add caching headers (cache for 1 hour)
        self.send_header('Cache-Control', 'public, max-age=3600')
        super().end_headers()

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        """Log with timestamp."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def get_local_ip():
    """Get the local IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_self_signed_cert(cert_file: Path, key_file: Path):
    """Generate a self-signed SSL certificate if it doesn't exist."""
    if cert_file.exists() and key_file.exists():
        print(f"Using existing certificate: {cert_file}")
        return True

    print("Generating self-signed SSL certificate...")
    print("Note: For production, use a proper SSL certificate from a CA like Let's Encrypt")

    try:
        import subprocess
        result = subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', str(key_file),
            '-out', str(cert_file),
            '-days', '365',
            '-nodes',
            '-subj', '/CN=localhost'
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Generated certificate: {cert_file}")
            print(f"Generated key: {key_file}")
            return True
        else:
            print(f"OpenSSL error: {result.stderr}")
            return False
    except FileNotFoundError:
        print("Error: openssl not found. Please install openssl to generate certificates.")
        print("On Ubuntu/Debian: sudo apt install openssl")
        print("On macOS: brew install openssl")
        return False


def main():
    parser = argparse.ArgumentParser(description='Serve YouTube player HTML with HTTPS and CORS')
    parser.add_argument('--port', type=int, default=8443, help='Port to listen on (default: 8443)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--no-https', action='store_true', help='Use HTTP instead of HTTPS (not recommended)')
    args = parser.parse_args()

    # Get the directory containing the player HTML files
    script_dir = Path(__file__).parent.resolve()
    assets_dir = script_dir / 'packages' / 'youtube_player_iframe' / 'assets'

    if not assets_dir.exists():
        print(f"Error: Assets directory not found: {assets_dir}")
        sys.exit(1)

    player_html = assets_dir / 'player_remote.html'
    if not player_html.exists():
        print(f"Error: Player HTML not found: {player_html}")
        sys.exit(1)

    # Create a symlink or copy player_remote.html as player.html for cleaner URL
    served_player = assets_dir / 'player.html'
    if not served_player.exists() or os.readlink(served_player) if served_player.is_symlink() else False != str(player_html):
        if served_player.exists() and not served_player.is_symlink():
            served_player.unlink()
        if served_player.is_symlink():
            served_player.unlink()
        os.symlink('player_remote.html', served_player)
        print(f"Created symlink: {served_player} -> player_remote.html")

    # Change to assets directory for serving
    os.chdir(assets_dir)

    local_ip = get_local_ip()

    if args.no_https:
        # HTTP server (not recommended - YouTube requires HTTPS for embeds)
        print("\n" + "=" * 60)
        print("WARNING: Running in HTTP mode. This may not work with YouTube embeds!")
        print("YouTube requires HTTPS for embedded players.")
        print("=" * 60 + "\n")

        server = http.server.HTTPServer((args.host, args.port), CORSRequestHandler)
        protocol = "http"
    else:
        # HTTPS server
        cert_dir = script_dir / 'certs'
        cert_dir.mkdir(exist_ok=True)

        cert_file = cert_dir / 'cert.pem'
        key_file = cert_dir / 'key.pem'

        if not generate_self_signed_cert(cert_file, key_file):
            print("Failed to generate SSL certificate. Use --no-https for HTTP mode.")
            sys.exit(1)

        server = http.server.HTTPServer((args.host, args.port), CORSRequestHandler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cert_file), str(key_file))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        protocol = "https"

    print("\n" + "=" * 60)
    print("YouTube Player HTML Server")
    print("=" * 60)
    print(f"\nServer running at:")
    print(f"  Local:   {protocol}://localhost:{args.port}/player.html")
    print(f"  Network: {protocol}://{local_ip}:{args.port}/player.html")
    print(f"\nServing files from: {assets_dir}")
    print("\nIn your Flutter app, use:")
    print(f'''
  YoutubePlayerController(
    params: YoutubePlayerParams(
      playerUrl: '{protocol}://{local_ip}:{args.port}/player.html',
      // ... other params
    ),
  );
''')
    print("=" * 60)
    print("\nPress Ctrl+C to stop the server\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        server.shutdown()


if __name__ == '__main__':
    main()
