from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from metadata import DISPLAY_SCHEMA
from parser_engine import QueryProcessor, SQLValidationError, layout_tree


EXAMPLE_QUERY = (
    "SELECT cliente.nome, pedido.idPedido, produto.nome, pedido_has_produto.quantidade "
    "FROM cliente "
    "JOIN pedido ON cliente.idCliente = pedido.Cliente_idCliente "
    "JOIN pedido_has_produto ON pedido.idPedido = pedido_has_produto.Pedido_idPedido "
    "JOIN produto ON produto.idProduto = pedido_has_produto.Produto_idProduto "
    "WHERE pedido.valorTotalPedido > 100 AND produto.preco >= 10"
)


class QueryProcessorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('Projeto 2 - Processador de Consultas')
        self.root.geometry('1300x860')

        self.processor = QueryProcessor()
        self._build_layout()
        self._fill_schema()
        self.sql_text.insert('1.0', EXAMPLE_QUERY)

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=10)
        container.pack(fill='both', expand=True)

        header = ttk.Label(
            container,
            text='Processador de Consultas SQL → Álgebra Relacional → Grafo Otimizado',
            font=('Arial', 14, 'bold')
        )
        header.pack(anchor='w', pady=(0, 8))

        top_frame = ttk.Frame(container)
        top_frame.pack(fill='x', pady=(0, 10))

        left_top = ttk.Frame(top_frame)
        left_top.pack(side='left', fill='both', expand=True)

        ttk.Label(left_top, text='Digite a consulta SQL:').pack(anchor='w')
        self.sql_text = tk.Text(left_top, height=8, wrap='word', font=('Consolas', 10))
        self.sql_text.pack(fill='x', expand=True)

        button_bar = ttk.Frame(left_top)
        button_bar.pack(fill='x', pady=(8, 0))
        ttk.Button(button_bar, text='Processar consulta', command=self.process_query).pack(side='left')
        ttk.Button(button_bar, text='Inserir exemplo', command=self.insert_example).pack(side='left', padx=6)
        ttk.Button(button_bar, text='Limpar', command=self.clear_all).pack(side='left')

        right_top = ttk.LabelFrame(top_frame, text='Metadados válidos (Imagem 01)', padding=8)
        right_top.pack(side='right', fill='both', padx=(10, 0))
        self.schema_text = tk.Text(right_top, width=42, height=13, wrap='word', font=('Consolas', 9))
        self.schema_text.pack(fill='both', expand=True)
        self.schema_text.configure(state='disabled')

        notebook = ttk.Notebook(container)
        notebook.pack(fill='both', expand=True)

        self.tab_result = ttk.Frame(notebook)
        self.tab_graph = ttk.Frame(notebook)
        self.tab_plan = ttk.Frame(notebook)
        notebook.add(self.tab_result, text='Resultados')
        notebook.add(self.tab_graph, text='Grafos')
        notebook.add(self.tab_plan, text='Plano de execução')

        self._build_result_tab()
        self._build_graph_tab()
        self._build_plan_tab()

    def _build_result_tab(self) -> None:
        frame = self.tab_result
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        ttk.Label(frame, text='SQL normalizado').grid(row=0, column=0, sticky='w', padx=8, pady=(8, 2))
        self.sql_normalized = tk.Text(frame, height=6, wrap='word', font=('Consolas', 10))
        self.sql_normalized.grid(row=1, column=0, sticky='nsew', padx=8)

        ttk.Label(frame, text='Álgebra relacional').grid(row=0, column=1, sticky='w', padx=8, pady=(8, 2))
        self.algebra_text = tk.Text(frame, height=6, wrap='word', font=('Consolas', 10))
        self.algebra_text.grid(row=1, column=1, sticky='nsew', padx=8)

        ttk.Label(frame, text='Grafo original em texto').grid(row=2, column=0, sticky='w', padx=8, pady=(8, 2))
        self.original_text_graph = tk.Text(frame, wrap='none', font=('Consolas', 10))
        self.original_text_graph.grid(row=3, column=0, sticky='nsew', padx=8, pady=(0, 8))

        ttk.Label(frame, text='Grafo otimizado em texto').grid(row=2, column=1, sticky='w', padx=8, pady=(8, 2))
        self.optimized_text_graph = tk.Text(frame, wrap='none', font=('Consolas', 10))
        self.optimized_text_graph.grid(row=3, column=1, sticky='nsew', padx=8, pady=(0, 8))

    def _build_graph_tab(self) -> None:
        frame = self.tab_graph
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(frame, text='Grafo original').grid(row=0, column=0, sticky='w', padx=8, pady=(8, 2))
        ttk.Label(frame, text='Grafo otimizado').grid(row=0, column=1, sticky='w', padx=8, pady=(8, 2))

        self.original_canvas = tk.Canvas(frame, bg='white', height=620)
        self.original_canvas.grid(row=1, column=0, sticky='nsew', padx=8, pady=(0, 8))
        self.optimized_canvas = tk.Canvas(frame, bg='white', height=620)
        self.optimized_canvas.grid(row=1, column=1, sticky='nsew', padx=8, pady=(0, 8))

    def _build_plan_tab(self) -> None:
        frame = self.tab_plan
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(frame, text='Ordem de execução conforme o grafo otimizado').grid(
            row=0, column=0, sticky='w', padx=8, pady=(8, 2)
        )
        self.execution_text = tk.Text(frame, wrap='word', font=('Consolas', 10))
        self.execution_text.grid(row=1, column=0, sticky='nsew', padx=8, pady=(0, 8))

    def _fill_schema(self) -> None:
        self.schema_text.configure(state='normal')
        self.schema_text.delete('1.0', 'end')
        for table, columns in DISPLAY_SCHEMA.items():
            self.schema_text.insert('end', f'{table}:\n')
            self.schema_text.insert('end', f'  {", ".join(columns)}\n\n')
        self.schema_text.configure(state='disabled')

    def insert_example(self) -> None:
        self.sql_text.delete('1.0', 'end')
        self.sql_text.insert('1.0', EXAMPLE_QUERY)

    def clear_all(self) -> None:
        self.sql_text.delete('1.0', 'end')
        for widget in [
            self.sql_normalized,
            self.algebra_text,
            self.original_text_graph,
            self.optimized_text_graph,
            self.execution_text,
        ]:
            widget.delete('1.0', 'end')
        self.original_canvas.delete('all')
        self.optimized_canvas.delete('all')

    def process_query(self) -> None:
        sql = self.sql_text.get('1.0', 'end').strip()
        if not sql:
            messagebox.showwarning('Aviso', 'Digite uma consulta SQL antes de processar.')
            return

        try:
            result = self.processor.process(sql)
        except SQLValidationError as exc:
            messagebox.showerror('Erro de validação', str(exc))
            return
        except Exception as exc:
            messagebox.showerror('Erro inesperado', f'Ocorreu um erro ao processar a consulta:\n{exc}')
            return

        self._put_text(self.sql_normalized, result['normalized_sql'])
        self._put_text(self.algebra_text, result['relational_algebra'])
        self._put_text(self.original_text_graph, result['text_graph_original'])
        self._put_text(self.optimized_text_graph, result['text_graph_optimized'])
        self._put_text(self.execution_text, '\n'.join(result['execution_plan']))

        self._draw_graph(self.original_canvas, result['original_graph'])
        self._draw_graph(self.optimized_canvas, result['optimized_graph'])

    def _put_text(self, widget: tk.Text, text: str) -> None:
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)

    def _draw_graph(self, canvas: tk.Canvas, root) -> None:
        canvas.delete('all')
        nodes = layout_tree(root)
        if not nodes:
            return

        canvas.update_idletasks()
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 400)

        max_x = max(node.x for node in nodes) or 1
        max_y = max(node.y for node in nodes) or 1
        x_margin = 70
        y_margin = 50
        x_scale = (width - 2 * x_margin) / max(max_x, 1)
        y_scale = (height - 2 * y_margin) / max(max_y, 1)

        positions = {}
        for node in nodes:
            x = x_margin + node.x * x_scale
            y = y_margin + node.y * y_scale
            positions[id(node)] = (x, y)

        for node in nodes:
            x1, y1 = positions[id(node)]
            for child in node.children:
                x2, y2 = positions[id(child)]
                canvas.create_line(x1, y1 + 20, x2, y2 - 20, width=2)

        for node in nodes:
            x, y = positions[id(node)]
            text = node.label
            box_width = min(max(130, len(text) * 7), 260)
            box_height = 46
            canvas.create_rectangle(x - box_width / 2, y - box_height / 2, x + box_width / 2, y + box_height / 2)
            canvas.create_text(x, y, text=text, width=box_width - 10, font=('Arial', 9, 'bold'))


def main() -> None:
    root = tk.Tk()
    app = QueryProcessorApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
