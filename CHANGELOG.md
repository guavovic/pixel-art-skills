# Changelog

## Não lançado

- **Instalação pelo PyPI:** o pacote saiu no PyPI (https://pypi.org/p/pixel-art-skills) em 02/11/2026; README, referência e todas as embalagens passam a instalar com `pip install "pixel-art-skills[mcp]"`.
- **Servidor MCP por HTTP:** `mcp --http` sobe o servidor em streamable-http com um token obrigatório na URL, para usar o ateliê pelos chats do navegador (claude.ai e ChatGPT) através de um túnel como o do Cloudflare. O stdio continua o padrão. Passo a passo em `docs/referencia.md`, seção Chats do navegador.
- **Documentação:** seção "Limites conhecidos" na referência, com o que o `revisar` e o `ref` não pegam ou alertam à toa (legibilidade, pillow e serrilhado sem camadas, composição repetida, linha 2:1 da nuvem, pontilhado e contorno no `ref`) e as medições de 27/10/2026.

## v0.1.0 (27/10/2026)

Primeira versão.

- **gerar:** cena inteira a partir de uma receita JSON, em camadas do fundo para a frente (céu, nuvens, montanhas, árvores, rochas, cristais, névoa e raios), cada uma com laço horizontal sem emenda e resultado determinístico pela seed.
- **Estilos:** metroidvania-noturno, snes-diurno e game-boy, com paleta, rampas e atmosfera próprias.
- **Gerações:** a mesma receita em 8, 16 ou 32 bits ou moderna, com resolução, cores, sombreamento, contorno e textura de cada época.
- **Animação:** as camadas andam num laço que fecha sem emenda, em GIF e folha de quadros.
- **revisar:** conferência em texto de cores, contraste, legibilidade, pixel solto, pillow shading, serrilhado, emenda do laço e limites da geração, com o lugar de cada problema e o capítulo do guia que explica.
- **ref:** uma imagem de referência vira paleta e rampas gravadas como preset com nome.
- **Guia de pixel art** dividido por capítulo.
- **Servidor MCP** local com as ferramentas do pacote.
- **Embalagens** para Claude Code, OpenAI Codex, Gemini CLI, Antigravity CLI, Cursor e GitHub Copilot, geradas por `scripts/embalar.py`.
