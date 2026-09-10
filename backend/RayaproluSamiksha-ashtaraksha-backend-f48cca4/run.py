"""Convenient standalone startup; uses the local dependency folder when available."""
import argparse
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
if (root / '.deps').exists():
    sys.path.insert(0, str(root / '.deps'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--dev', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be 1-65535')
    import server
    server.initialize()
    if args.dev:
        print(f'Ashtaraksha development API: http://{args.host}:{args.port}', flush=True)
        server.ThreadingHTTPServer((args.host, args.port), server.Handler).serve_forever()
    else:
        try:
            from waitress import serve
        except ImportError:
            parser.error('Install requirements.txt, or use --dev for the dependency-free server')
        from app import application
        print(f'Ashtaraksha API: http://{args.host}:{args.port}', flush=True)
        serve(application, host=args.host, port=args.port, threads=8, max_request_body_size=14_100_000)
