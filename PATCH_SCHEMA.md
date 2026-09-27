# Live Translator Community Patch — schema v1

Os patches comunitários são exportados pelo próprio Live Translator.

```json
{
  "schemaVersion": 1,
  "modName": "PathOfTerraria",
  "modVersion": "0.3.13",
  "language": "pt-BR",
  "createdAt": "2026-09-27T18:00:00Z",
  "entries": [
    {
      "key": "Mods.PathOfTerraria.UI.AreaLevel",
      "original": "Area Level",
      "translation": "Nível da Área"
    },
    {
      "key": null,
      "original": "Hardcoded text",
      "translation": "Texto hardcoded"
    }
  ]
}
```

## Campos

- `schemaVersion`: versão do formato.
- `modName`: nome interno do mod.
- `modVersion`: versão do mod usada na criação.
- `language`: idioma de destino.
- `createdAt`: data UTC da exportação.
- `entries`: traduções do patch.
- `key`: chave de localização quando ela existe; `null` para textos hardcoded/dinâmicos.
- `original`: texto original.
- `translation`: tradução escolhida pelo criador.

O autor e os selos de confiança não são determinados pelo JSON. A autoria vem da conta que abriu a Issue; selos como `verified` devem vir das labels da Issue.
