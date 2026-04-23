# AV 2 - Processador de Consultas

Este projeto foi desenvolvido para atender ao trabalho **Processador de Consultas** da disciplina de **Banco de Dados**.

## O que o sistema faz

A aplicação possui interface gráfica em **Tkinter** e implementa o fluxo pedido no PDF:

1. recebe a consulta SQL;
2. normaliza a string ignorando maiúsculas/minúsculas e espaços extras;
3. valida sintaxe básica, tabelas e atributos do modelo fornecido;
4. converte a consulta para álgebra relacional;
5. constrói o grafo de operadores original;
6. aplica heurísticas de otimização;
7. exibe o grafo otimizado;
8. mostra o plano de execução ordenado.

## Histórias de usuário atendidas

### HU1 - Entrada e validação da consulta
- Campo de entrada SQL na interface.
- Validação dos comandos SELECT, FROM, WHERE, JOIN e ON.
- Validação dos operadores =, >, <, <=, >= e <>.
- Verificação de existência de tabelas, atributos e aliases.
- Suporte a múltiplos JOINs.
- Ignora diferenças entre letras maiúsculas/minúsculas.
- Ignora repetições de espaços em branco.

### HU2 - Conversão para álgebra relacional
- Exibe a expressão equivalente usando projeção `π`, seleção `σ` e junção `⋈`.
- Preserva condições de filtro e de junção.

### HU3 - Construção do grafo de operadores
- Gera o grafo em memória.
- Exibe o grafo em texto e também desenhado em canvas.
- Folhas representam tabelas.
- Nós internos representam seleção, projeção e junção.
- A raiz representa a projeção final.

### HU4 - Otimização da consulta
- Aplica seleção cedo nas tabelas quando possível.
- Aplica projeção cedo para reduzir atributos intermediários.
- Reordena junções priorizando partes mais restritivas.
- Evita produto cartesiano exigindo condição em cada JOIN.
- Exibe o grafo otimizado.

### HU5 - Plano de execução
- Exibe a ordem das operações conforme o grafo otimizado.
- Lista cada etapa em sequência.

## Estrutura dos arquivos

- `main.py` -> interface gráfica
- `parser_engine.py` -> parsing, validação, álgebra relacional, otimização, grafo e plano de execução
- `metadata.py` -> metadados das tabelas e atributos do modelo do trabalho
- `requirements.txt` -> dependências

## Como executar

### 1. Entre na pasta do projeto
```bash
cd query_processor_project
```

### 2. Execute o programa
```bash
python main.py
```

## Exemplo de consulta

```sql
SELECT cliente.nome, pedido.idPedido, produto.nome, pedido_has_produto.quantidade
FROM cliente
JOIN pedido ON cliente.idCliente = pedido.Cliente_idCliente
JOIN pedido_has_produto ON pedido.idPedido = pedido_has_produto.Pedido_idPedido
JOIN produto ON produto.idProduto = pedido_has_produto.Produto_idProduto
WHERE pedido.valorTotalPedido > 100 AND produto.preco >= 10
```

## Observações

- O projeto foi focado exatamente no subconjunto SQL pedido no enunciado.
- Não executa a consulta em banco real; o objetivo é didático: parsing, representação lógica, otimização heurística e plano de execução.
- O modelo de dados usado na validação segue o conjunto de tabelas informado no PDF do trabalho.
