import os
import http.server
import socketserver
import webbrowser
from urllib.parse import urlparse, parse_qs

# Set the directory containing your HTML and JSON files
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(WEB_DIR)

# Port to serve on
PORT = 8000

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Handle any specific routes
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def log_message(self, format, *args):
        
        print(f"[SERVER] {self.client_address[0]} - {format % args}")

# Create the server
Handler = MyHandler
httpd = socketserver.TCPServer(("", PORT), Handler)

print(f" Server started at http://localhost:{PORT}")
print(f" Serving files from: {WEB_DIR}")
print(" Opening browser...")

# Open the browser
webbrowser.open(f"http://localhost:{PORT}/maps.html")

print(" Press Ctrl+C to stop the server")

# Start the server
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\n Server stopped")
    httpd.server_close()