# Desenho: webhook Telegram para RabbitMQ

## Objetivo e escopo

Criar um serviço Python pequeno para receber atualizações enviadas pelo Telegram ao webhook e colocá-las em uma fila RabbitMQ. A aplicação não processa mensagens; consumidores ficam fora deste escopo. Não haverá autenticação própria nesta primeira versão, conforme solicitado.

## Abordagens consideradas

- **Flask + `pika`**: fluxo HTTP síncrono simples, alinhado ao cliente síncrono do RabbitMQ. **Escolhida** por manter poucas dependências e conceitos.
- **FastAPI + `pika`**: validação de entrada mais estruturada, mas o cliente síncrono pode bloquear o servidor assíncrono e exigir trabalho adicional.

## Comportamento proposto

- Expor `POST /telegram/webhook` para receber o JSON de uma atualização do Telegram.
- Publicar o JSON completo, sem transformar o conteúdo, em uma fila configurável (padrão sugerido: `telegram_updates`).
- Declarar a fila durável e publicar mensagens persistentes para que atualizações sobrevivam a uma reinicialização normal do RabbitMQ.
- Retornar sucesso ao Telegram somente após a publicação ser confirmada; se o RabbitMQ estiver indisponível, retornar erro HTTP para permitir nova tentativa.
- Ler URI do RabbitMQ e nome da fila de variáveis de ambiente. A URI será fornecida pelo responsável pela implantação; nenhum endereço será embutido no código.
- Não incluir processamento de mensagens, painel, banco de dados, autenticação própria, configuração automática do webhook ou suporte a múltiplos bots.

## Desenvolvimento e configuração

Usar Flask e `pika`, com dependências e instruções de execução documentadas. Um arquivo `.env.example` pode mostrar os nomes das variáveis sem conter credenciais. A URL pública do serviço e a configuração do webhook no Telegram serão responsabilidades da implantação. Não é necessário incluir RabbitMQ local em Docker Compose nesta etapa.

## Critérios de aceite

Uma atualização recebida é enfileirada como JSON preservado; uma falha ao publicar não é reportada ao Telegram como sucesso; configuração ausente ou inválida produz erro claro no início do serviço. O endpoint será público e sem autenticação nesta primeira versão, como solicitado.
