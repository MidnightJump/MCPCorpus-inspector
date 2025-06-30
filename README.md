# MCPCorpus: A Large-Scale Evolvable Dataset for Model Context Protocol Ecosystem and Security Analysis

**MCPCorpus** is a comprehensive dataset for analyzing the Model Context Protocol (MCP) ecosystem, containing ~14K MCP servers and 300 MCP clients with 20+ normalized metadata attributes.

## 📊 Dataset Overview

- **Scale**: ~14K MCP servers + 300 MCP clients
- **Attributes**: 20+ normalized metadata per artifact
- **Sources**: GitHub, community hubs, package managers
- **Applications**: Ecosystem analysis, security research, interoperability studies

## 📁 Structure

```
MCPCorpus/
├── Crawler/                    # Data collection tools
│   ├── Servers/               # Server data (mcpso_servers_cleaned.json)
│   ├── Clients/               # Client data (mcpso_clients_cleaned.json)
│   ├── github_info_collector.py  # GitHub metadata collector
│   └── data_cleaner.py        # Data normalization
└── Website/                   # Web search interface
    ├── server.py              # Local web server
    └── index.html             # Search interface
```

## 🚀 Quick Start

### Explore Dataset
```bash
cd Website
python server.py
# Open http://localhost:8000
```

### Access Data Programmatically
```python
import json
import pandas as pd

# Load datasets
with open('Crawler/Servers/mcpso_servers_cleaned.json', 'r') as f:
    servers = json.load(f)
with open('Crawler/Clients/mcpso_clients_cleaned.json', 'r') as f:
    clients = json.load(f)

# Convert to DataFrame
servers_df = pd.DataFrame(servers)
clients_df = pd.DataFrame(clients)
```

### Update Dataset (Optional)
```bash
# Collect new data
cd Crawler/Servers && python Server_request.py
cd ../Clients && python Client_request.py

# Add GitHub metadata
cd .. && python github_info_collector.py --token YOUR_GITHUB_TOKEN
```


