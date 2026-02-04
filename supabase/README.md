# Supabase SQL Scripts

Ce dossier contient les scripts SQL à exécuter dans Supabase.

## Ordre d'exécution

1. **001_schema.sql** - Schéma initial (tables, index, vues, fonctions)
   - Exécute ce fichier en premier dans le SQL Editor de Supabase

## Comment exécuter

1. Connecte-toi à ton dashboard Supabase
2. Va dans "SQL Editor" (icône dans la sidebar)
3. Clique sur "New Query"
4. Copie-colle le contenu du fichier SQL
5. Clique sur "Run" (ou Ctrl+Enter)

## Tables créées

| Table | Description |
|-------|-------------|
| `agents` | Informations des agents IA (Grok, DeepSeek, GPT, Consortium) |
| `trades` | Historique de tous les trades |
| `positions` | Positions actuelles de chaque agent |
| `performance_snapshots` | Snapshots pour les graphiques |
| `autocritiques` | Historique des autocritiques |
| `market_data_cache` | Cache des données de marché |
| `trading_sessions` | Sessions de trading |

## Vues disponibles

- `leaderboard` - Classement des agents par performance
- `recent_trades` - 100 derniers trades
- `positions_summary` - Résumé des positions par agent

## Fonctions

- `update_updated_at()` - Trigger pour mettre à jour automatiquement `updated_at`
- `calculate_win_rate(agent_uuid)` - Calcule le taux de réussite d'un agent
