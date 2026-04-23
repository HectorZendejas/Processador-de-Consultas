SCHEMA = {
    'categoria': ['idcategoria', 'descricao'],
    'produto': ['idproduto', 'nome', 'descricao', 'preco', 'quantestoque', 'categoria_idcategoria'],
    'tipocliente': ['idtipocliente', 'descricao'],
    'cliente': ['idcliente', 'nome', 'email', 'nascimento', 'senha', 'tipocliente_idtipocliente', 'dataregistro'],
    'tipoendereco': ['idtipoendereco', 'descricao'],
    'endereco': ['idendereco', 'enderecopadrao', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf', 'cep', 'tipoendereco_idtipoendereco', 'cliente_idcliente'],
    'telefone': ['numero', 'cliente_idcliente'],
    'status': ['idstatus', 'descricao'],
    'pedido': ['idpedido', 'status_idstatus', 'datapedido', 'valortotalpedido', 'cliente_idcliente'],
    'pedido_has_produto': ['idpedidoproduto', 'pedido_idpedido', 'produto_idproduto', 'quantidade', 'precounitario'],
}

DISPLAY_SCHEMA = {
    'Categoria': ['idCategoria', 'Descricao'],
    'Produto': ['idProduto', 'Nome', 'Descricao', 'Preco', 'QuantEstoque', 'Categoria_idCategoria'],
    'TipoCliente': ['idTipoCliente', 'Descricao'],
    'Cliente': ['idCliente', 'Nome', 'Email', 'Nascimento', 'Senha', 'TipoCliente_idTipoCliente', 'DataRegistro'],
    'TipoEndereco': ['idTipoEndereco', 'Descricao'],
    'Endereco': ['idEndereco', 'EnderecoPadrao', 'Logradouro', 'Numero', 'Complemento', 'Bairro', 'Cidade', 'UF', 'CEP', 'TipoEndereco_idTipoEndereco', 'Cliente_idCliente'],
    'Telefone': ['Numero', 'Cliente_idCliente'],
    'Status': ['idStatus', 'Descricao'],
    'Pedido': ['idPedido', 'Status_idStatus', 'DataPedido', 'ValorTotalPedido', 'Cliente_idCliente'],
    'Pedido_has_Produto': ['idPedidoProduto', 'Pedido_idPedido', 'Produto_idProduto', 'Quantidade', 'PrecoUnitario'],
}

KEYWORDS = {
    'select', 'from', 'where', 'join', 'on', 'and'
}

OPERATORS = ['<=', '>=', '<>', '=', '>', '<']
