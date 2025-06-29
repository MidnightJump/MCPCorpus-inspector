#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Servers Data Cleaning Script
Keep only user-specified core fields and simplify data structure
"""

import json
import os
from typing import Dict, Any, List

def clean_server_data(original_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean server data, keep only specified fields, and filter out items without URLs
    """
    cleaned_data = []
    filtered_count = 0
    
    for item in original_data:
        # Filter out items without URLs
        url = item.get('url')
        if not url or url.strip() == '':
            filtered_count += 1
            continue
            
        metadata = item.get('metadata', {})
        github = item.get('github', {})
        
        # Build cleaned data structure
        cleaned_item = {
            # Unique identifier
            "id": metadata.get('id'),
            
            # Basic information
            "name": item.get('name'),
            "url": url,
            
            # metadata core fields
            "title": metadata.get('title'),
            "description": metadata.get('description'),
            "author_name": metadata.get('author_name'),
            "tags": metadata.get('tags'),
            "category": metadata.get('category'),
            "type": metadata.get('type'),
            "tools": metadata.get('tools'),
            "sse_url": metadata.get('sse_url'),
            "server_command": metadata.get('server_command'),
            "server_config": metadata.get('server_config'),
            
            # github complete object
            "github": github if github else None
        }
        
        cleaned_data.append(cleaned_item)
    
    print(f"Filtered out items without URLs: {filtered_count} records")
    return cleaned_data

def main():
    """Main function"""
    input_file = 'mcpso_servers.json'
    output_file = 'mcpso_servers_cleaned.json'
    
    # Check input file
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return
    
    # Read original data
    print(f"📖 Reading original data: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        original_data = json.load(f)
    
    print(f"Original data count: {len(original_data)}")
    
    # Clean data
    print("🧹 Starting data cleaning...")
    cleaned_data = clean_server_data(original_data)
    
    # Statistics
    github_count = sum(1 for item in cleaned_data if item.get('github'))
    print(f"Cleaned data count: {len(cleaned_data)}")
    print(f"Contains GitHub information: {github_count} records")
    
    # Write cleaned data
    print(f"💾 Writing cleaned data: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
    
    # Calculate file size change
    original_size = os.path.getsize(input_file) / 1024 / 1024  # MB
    cleaned_size = os.path.getsize(output_file) / 1024 / 1024  # MB
    size_reduction = (1 - cleaned_size / original_size) * 100
    
    print(f"\n📊 Cleaning Results:")
    print(f"Original file size: {original_size:.2f} MB")
    print(f"Cleaned file size: {cleaned_size:.2f} MB")
    print(f"Size reduction: {size_reduction:.1f}%")
    print(f"✅ Data cleaning completed!")

if __name__ == "__main__":
    main() 