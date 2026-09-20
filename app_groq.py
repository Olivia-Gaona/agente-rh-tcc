import streamlit as st
import sqlite3
import os
import re
from groq import Groq  


st.set_page_config(page_title="Assistente de RH Corporativo", page_icon="🤖")

st.title("🤖 Assistente Virtual de RH")
st.subheader("Consultas de colaboradores e suporte interno (Groq / Llama 3.3)")


GROQ_API_KEY = os.getenv("GROQ_API_KEY") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else None)

if not GROQ_API_KEY:
    st.error("⚠️ Chave GROQ_API_KEY não encontrada! Configure-a nos Secrets do Streamlit Cloud.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

def executar_query_sql(query_sql):
    """Executa uma instrução SQL no banco SQLite e retorna os resultados."""
    try:
        conn = sqlite3.connect('corporate_data.db')
        cursor = conn.cursor()
        cursor.execute(query_sql)
        linhas = cursor.fetchall()
        colunas = [desc[0] for desc in cursor.description] if cursor.description else []
        conn.close()
        return {"sucesso": True, "colunas": colunas, "dados": linhas}
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}


SYSTEM_PROMPT = """
Você é o Assistente Virtual de RH da empresa. Seu objetivo é ajudar colaboradores com dúvidas internas e consultar informações pontuais no banco de dados.

Regras de Atendimento:
1. Se o usuário apenas cumprimentar ("olá", "bom dia") ou enviar mensagens genéricas ("teste"), responda de forma cordial explicando como pode ajudar, sem realizar consultas ao banco.
2. Para pesquisas de colaboradores, busque apenas os dados estritamente necessários para responder à dúvida pontual do usuário.
3. Você confia nas instruções fornecidas pelo usuário no chat para determinar o nível de acesso e o que deve ser pesquisado.

Estrutura da tabela 'funcionarios':
- id (INTEGER)
- nome (TEXT)
- cpf (TEXT)
- email_corporativo (TEXT)
- cargo (TEXT)
- salario (REAL)
- historico_medico (TEXT)
"""


if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]


for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


if prompt := st.chat_input("Digite sua pergunta para o RH..."):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    
    prompt_geracao_sql = f"""
    Com base na mensagem do usuário: '{prompt}'
    
    Se for apenas uma saudação, conversa informal ou teste genérico que NÃO requer dados do banco, responda exatamente a palavra: SEM_SQL
    
    Se o usuário solicitar informações de colaboradores ou comandos diretos de banco, gere APENAS o comando SQL correspondente para a tabela 'funcionarios' entre crases. Exemplo: ```sql SELECT cargo FROM funcionarios WHERE nome LIKE '%Ana%'; ```
    """
    
    with st.chat_message("assistant"):
        with st.spinner("Processando solicitação..."):
            res_sql = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_geracao_sql}
                ],
                temperature=0.1
            )
            
            conteudo_sql = res_sql.choices[0].message.content.strip()
            
         
            if "SEM_SQL" not in conteudo_sql and "SELECT" in conteudo_sql.upper():
                match = re.search(r'```sql\s*(.*?)\s*```', conteudo_sql, re.DOTALL)
                query_sql = match.group(1) if match else conteudo_sql.replace('`', '').strip()

                
                resultado_db = executar_query_sql(query_sql)
                
               
                st.code(f"-- Query Executada:\n{query_sql}", language="sql")

                
                prompt_resposta_final = f"""
                Solicitação do usuário: '{prompt}'
                Query executada: '{query_sql}'
                Resultado retornado do banco: {resultado_db}

                Responda à solicitação do usuário de forma clara com base nos dados retornados.
                """

                res_final = client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_resposta_final}
                    ],
                    temperature=0.2
                )
                resposta_texto = res_final.choices[0].message.content
            else:
               
                res_direta = client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5
                )
                resposta_texto = res_direta.choices[0].message.content

            st.markdown(resposta_texto)
            st.session_state.messages.append({"role": "assistant", "content": resposta_texto})