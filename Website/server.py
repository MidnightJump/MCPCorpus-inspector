#!/usr/bin/env python3
"""
Simple HTTP server for running MCP data display website
"""

import http.server
import socketserver
import json
import os
import webbrowser
from pathlib import Path

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers to allow local file access
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_GET(self):
        # Redirect root path to display page
        if self.path == '/':
            self.path = '/index.html'
        
        # Handle JSON file requests, ensure correct Content-Type
        if self.path.endswith('.json'):
            try:
                # Get file path
                file_path = self.path.lstrip('/')
                
                # Check if file exists
                if os.path.exists(file_path):
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.end_headers()
                    
                    # Read and send JSON file
                    with open(file_path, 'rb') as f:
                        self.wfile.write(f.read())
                    return
                else:
                    self.send_error(404, f"File not found: {file_path}")
                    return
            except Exception as e:
                self.send_error(500, f"Error reading file: {str(e)}")
                return
        
        # Use default handling for other files
        super().do_GET()

def main():
    # Set server parameters
    PORT = 8000
    HOST = 'localhost'
    
    # Check if required files exist
    required_files = [
        'index.html',
        'styles.css', 
        'script.js',
        'mcpso_clients_cleaned.json',
        'mcpso_servers_cleaned.json'
    ]
    
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print(f"❌ Missing required files: {', '.join(missing_files)}")
        return
    
    # Create server
    with socketserver.TCPServer((HOST, PORT), CustomHTTPRequestHandler) as httpd:
        print(f"🌐 MCP data display website started successfully!")
        print(f"📍 Server address: http://{HOST}:{PORT}")
        print(f"🔗 Access link: http://{HOST}:{PORT}/index.html")
        print(f"⏹️  Press Ctrl+C to stop server")
        print()
        
        # Try to automatically open browser
        try:
            webbrowser.open(f'http://{HOST}:{PORT}/index.html')
            print("🎉 Browser opened automatically")
        except:
            print("💡 Please manually open the above link in your browser")
        
        print()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Server stopped")

if __name__ == "__main__":
    main() 