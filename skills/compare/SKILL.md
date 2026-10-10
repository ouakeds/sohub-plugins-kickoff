---
name: compare
description: Compare plusieurs runs de cadrage (dossiers de projets générés à partir de la même idée) sur la qualité, le temps et le coût, à partir de leurs .sohub-plugin/metrics.jsonl. À utiliser quand l'utilisateur veut comparer des runs, des versions du plugin ou des modèles.
argument-hint: "<dossier projet> <dossier projet> …"
allowed-tools: Bash(python3:*), Glob, Read
---

Tu compares des runs de cadrage. Les chiffres viennent du script, jamais de toi.

Argument reçu : `$ARGUMENTS` (dossiers de projets ; peut être vide).

1. Si aucun dossier n'est donné, cherche les `*/.sohub-plugin/metrics.jsonl` du répertoire courant et compare tous les projets trouvés.
2. Lance `python3 "${CLAUDE_SKILL_DIR}/../../hooks/metrics.py" compare <dossiers…>` et montre le tableau tel quel.
3. Commente en quelques lignes, en ne citant que des chiffres du tableau :
   - **Qualité** : points d'ombre ouverts et bloquants au dernier eval, et la convergence d'une itération à l'autre ;
   - **Temps** : durée totale, et part des agents ;
   - **Coût** : coût total, la part de l'entrée par rapport à la sortie, et le coût par itération ;
   - le meilleur compromis entre qualité, temps et coût, en précisant ce qui diffère entre les runs (version du plugin, modèles · effort, étape atteinte, nombre d'itérations).
4. Signale les limites qui faussent la comparaison : runs arrêtés à des étapes différentes, nombre d'itérations différent, orchestrateur non mesuré. Rappelle aussi que la qualité est mesurée par l'agent évaluateur lui-même, donc deux runs ne se comparent qu'avec le même évaluateur (même version du plugin et même modèle).
