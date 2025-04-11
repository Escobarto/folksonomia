import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import os
from datetime import datetime
import hashlib
import base64
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Configuração inicial
st.set_page_config(page_title="Projeto Folksonomia", layout="wide")

# Criar diretórios e arquivos necessários se não existirem
if not os.path.exists("data"):
    os.makedirs("data")

if not os.path.exists("data/users.csv"):
    pd.DataFrame(columns=["user_id", "timestamp", "q1", "q2", "q3"]).to_csv("data/users.csv", index=False)

if not os.path.exists("data/tags.csv"):
    pd.DataFrame(columns=["user_id", "obra_id", "tag", "timestamp"]).to_csv("data/tags.csv", index=False)

if not os.path.exists("data/admin.csv"):
    # Criar senha padrão: admin/admin123
    admin_df = pd.DataFrame([{
        "username": "admin",
        "password": hashlib.sha256("admin123".encode()).hexdigest()
    }])
    admin_df.to_csv("data/admin.csv", index=False)

# Carregar dados das obras - modificada para resolver problema do cache
@st.cache_data(ttl=5, show_spinner=False)  # Expira o cache após 5 segundos
def load_obras():
    if os.path.exists("data/obras.csv"):
        obras_df = pd.read_csv("data/obras.csv")
        return obras_df.to_dict('records')
    else:
        # Dados iniciais se não houver arquivo
        obras = [
            {"id": 1, "titulo": "Guernica", "artista": "Pablo Picasso", "ano": "1937", 
             "imagem": "https://upload.wikimedia.org/wikipedia/en/7/74/PicassoGuernica.jpg"},
        ]
        # Salvar as obras iniciais
        pd.DataFrame(obras).to_csv("data/obras.csv", index=False)
        return obras

# Funções utilitárias
def generate_user_id():
    """Gera um ID único para o usuário"""
    return base64.b64encode(os.urandom(12)).decode('ascii')

def save_user_answers(user_id, answers):
    """Salva as respostas do questionário"""
    users_df = pd.read_csv("data/users.csv")
    new_row = pd.DataFrame([{
        "user_id": user_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "q1": answers["q1"],
        "q2": answers["q2"],
        "q3": answers["q3"]
    }])
    updated_df = pd.concat([users_df, new_row], ignore_index=True)
    updated_df.to_csv("data/users.csv", index=False)

def save_tag(user_id, obra_id, tag):
    """Salva uma tag associada a uma obra"""
    tags_df = pd.read_csv("data/tags.csv")
    new_row = pd.DataFrame([{
        "user_id": user_id,
        "obra_id": obra_id,
        "tag": tag.lower().strip(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }])
    updated_df = pd.concat([tags_df, new_row], ignore_index=True)
    updated_df.to_csv("data/tags.csv", index=False)

def get_tags_for_obra(obra_id):
    """Obtém todas as tags para uma obra específica"""
    tags_df = pd.read_csv("data/tags.csv")
    obra_tags = tags_df[tags_df["obra_id"] == obra_id]["tag"].value_counts().reset_index()
    if not obra_tags.empty:
        obra_tags.columns = ["tag", "count"]
        return obra_tags
    return pd.DataFrame(columns=["tag", "count"])

def check_admin_credentials(username, password):
    """Verifica as credenciais do administrador"""
    admin_df = pd.read_csv("data/admin.csv")
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    return ((admin_df["username"] == username) & (admin_df["password"] == hashed_password)).any()

# Funções para gráficos
def plot_tag_frequency(tags_df):
    """Gera um gráfico de barras das tags mais frequentes"""
    if tags_df.empty:
        return None
        
    all_tags = tags_df["tag"].value_counts().reset_index()
    all_tags.columns = ["tag", "count"]
    top_tags = all_tags.head(15)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top_tags["tag"], top_tags["count"])
    ax.set_title("Tags mais frequentes")
    ax.set_xlabel("Frequência")
    ax.set_ylabel("Tag")
    plt.tight_layout()
    return fig

def generate_wordcloud(tags_df):
    """Gera uma nuvem de palavras com as tags"""
    if tags_df.empty:
        return None
        
    tag_counts = tags_df["tag"].value_counts().to_dict()
    wc = WordCloud(width=800, height=400, background_color="white").generate_from_frequencies(tag_counts)
    
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation='bilinear')
    ax.axis("off")
    plt.tight_layout()
    return fig

def plot_tags_over_time(tags_df):
    """Gera um gráfico de linha mostrando a evolução do número de tags ao longo do tempo"""
    if tags_df.empty:
        return None
        
    tags_df["date"] = pd.to_datetime(tags_df["timestamp"]).dt.date
    tags_by_date = tags_df.groupby("date").size().reset_index(name="count")
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(tags_by_date["date"], tags_by_date["count"], marker='o')
    ax.set_title("Número de tags ao longo do tempo")
    ax.set_xlabel("Data")
    ax.set_ylabel("Número de tags")
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig

# Interface principal do Streamlit
def main():
    # Inicializar estado da sessão
    if 'user_id' not in st.session_state:
        st.session_state['user_id'] = generate_user_id()
    if 'step' not in st.session_state:
        st.session_state['step'] = 'intro'
    if 'answers' not in st.session_state:
        st.session_state['answers'] = {}

    # Barra lateral
    st.sidebar.title("Navegação")
    page = st.sidebar.radio("Ir para:", ["Início", "Explorar Obras", "Área Administrativa"])
    
    if page == "Início":
        show_intro()
    elif page == "Explorar Obras":
        show_obras()
    elif page == "Área Administrativa":
        show_admin()

def show_intro():
    st.title("Projeto de Folksonomia em Museus")
    st.write("""
    Bem-vindo ao nosso projeto de folksonomia! Estamos estudando como o público interage com acervos de museus,
    e sua participação é muito importante. Antes de começarmos, gostaríamos de fazer algumas perguntas rápidas.
    """)
    
    if st.session_state['step'] == 'intro':
        with st.form("intro_form"):
            st.write("### Questionário Inicial")
            q1 = st.selectbox(
                "Qual é o seu nível de familiaridade com museus?",
                ["Nunca visito museus", "Visito raramente", "Visito ocasionalmente", "Visito frequentemente"]
            )
            
            q2 = st.selectbox(
                "Você já ouviu falar sobre documentação museológica?",
                ["Nunca ouvi falar", "Já ouvi, mas não sei o que é", "Tenho uma ideia básica", "Conheço bem o tema"]
            )
            
            q3 = st.text_area(
                "O que você entende por 'tags' ou etiquetas digitais aplicadas a acervo?",
                max_chars=500
            )
            
            submit = st.form_submit_button("Enviar respostas")
            
            if submit:
                st.session_state['answers'] = {"q1": q1, "q2": q2, "q3": q3}
                save_user_answers(st.session_state['user_id'], st.session_state['answers'])
                st.session_state['step'] = 'completed'
                st.rerun()
    
    else:
        st.success("Obrigado por responder ao nosso questionário inicial! Agora você pode explorar as obras e adicionar suas tags.")
        #if st.button("Explorar Obras"):
            #st.session_state['step'] = 'obras'
            #st.rerun()

def show_obras():
    st.title("Explorar Obras")

    if st.session_state['step'] == 'intro':
        st.warning("Por favor, complete o questionário inicial antes de explorar as obras.")
        if st.button("Ir para o questionário"):
            st.rerun()
        return

    obras = load_obras()
    cols = st.columns(3)

    for i, obra in enumerate(obras):
        with cols[i % 3]:
            st.image(obra['imagem'], use_container_width=True)
            if st.button(f"Selecionar", key=f"btn_{obra['id']}"):
                st.session_state['selected_obra'] = obra
                st.rerun()

            if 'selected_obra' in st.session_state and st.session_state['selected_obra']['id'] == obra['id']:
                with st.form(f"tag_form_{obra['id']}"):
                    tag = st.text_input("Adicione uma tag para esta obra:")
                    submitted = st.form_submit_button("Enviar Tag")
                    if submitted and tag:
                        save_tag(st.session_state['user_id'], obra['id'], tag)
                        st.success(f"Tag '{tag}' adicionada com sucesso!")
                        st.rerun()

                #tags = get_tags_for_obra(obra['id'])
                #if not tags.empty:
                    #st.write("**Tags populares:**")
                    #for _, row in tags.iterrows():
                        #st.write(f"- {row['tag']} ({row['count']} vezes)")
               # else:
                    #st.write("Ainda não há tags para esta obra. Seja o primeiro a adicionar!")

def show_admin():
    st.title("Área Administrativa")
    
    # Login
    if 'admin_logged_in' not in st.session_state:
        st.session_state['admin_logged_in'] = False
        
    if not st.session_state['admin_logged_in']:
        with st.form("login_form"):
            st.write("### Login Administrativo")
            username = st.text_input("Usuário:")
            password = st.text_input("Senha:", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if check_admin_credentials(username, password):
                    st.session_state['admin_logged_in'] = True
                    st.rerun()
                else:
                    st.error("Credenciais inválidas. Tente novamente.")
    else:
        # Criar abas principais da área administrativa
        admin_tabs = st.tabs(["Análise de Dados", "Gerenciar Obras", "Gerenciar Administradores"])
        
        # Tab 1: Análise de Dados
        with admin_tabs[0]:
            st.write("### Análise de Dados")
            
            # Carregar dados
            tags_df = pd.read_csv("data/tags.csv")
            users_df = pd.read_csv("data/users.csv")
            
            # Métricas principais
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Usuários", len(users_df["user_id"].unique()))
            with col2:
                st.metric("Total de Tags", len(tags_df))
            with col3:
                st.metric("Tags Únicas", len(tags_df["tag"].unique()))
            
            # Guias para diferentes visualizações
            tab1, tab2, tab3, tab4 = st.tabs(["Frequência de Tags", "Nuvem de Palavras", "Tags ao Longo do Tempo", "Dados Brutos"])
            
            with tab1:
                st.write("### Tags mais frequentes")
                freq_fig = plot_tag_frequency(tags_df)
                if freq_fig:
                    st.pyplot(freq_fig)
                else:
                    st.write("Não há dados suficientes para gerar o gráfico.")
            
            with tab2:
                st.write("### Nuvem de Palavras")
                wc_fig = generate_wordcloud(tags_df)
                if wc_fig:
                    st.pyplot(wc_fig)
                else:
                    st.write("Não há dados suficientes para gerar a nuvem de palavras.")
            
            with tab3:
                st.write("### Evolução Temporal")
                time_fig = plot_tags_over_time(tags_df)
                if time_fig:
                    st.pyplot(time_fig)
                else:
                    st.write("Não há dados suficientes para gerar o gráfico.")
            
            with tab4:
                st.write("### Dados Brutos")
                
                st.subheader("Tags")
                st.dataframe(tags_df)
                
                # Opção para excluir tags
                with st.expander("Excluir dados de tags"):
                    st.warning("⚠️ Cuidado! Esta ação não pode ser desfeita.")
                    
                    delete_options = st.radio(
                        "Opções de exclusão:",
                        ["Excluir tag específica", "Excluir todas as tags de uma obra", "Excluir todas as tags"]
                    )
                    
                    if delete_options == "Excluir tag específica":
                        tag_to_delete = st.selectbox("Selecione a tag:", [""] + list(tags_df["tag"].unique()))
                        if tag_to_delete and st.button("Excluir tag selecionada"):
                            tags_df = tags_df[tags_df["tag"] != tag_to_delete]
                            tags_df.to_csv("data/tags.csv", index=False)
                            st.success(f"Tag '{tag_to_delete}' excluída com sucesso!")
                            st.rerun()
                    
                    elif delete_options == "Excluir todas as tags de uma obra":
                        obras = load_obras()
                        obra_options = {obra["id"]: f"{obra['titulo']} - {obra['artista']}" for obra in obras}
                        obra_to_delete = st.selectbox(
                            "Selecione a obra:", 
                            [""] + [f"{id}: {title}" for id, title in obra_options.items()]
                        )
                        
                        if obra_to_delete and st.button("Excluir tags da obra selecionada"):
                            obra_id = int(obra_to_delete.split(":")[0])
                            tags_df = tags_df[tags_df["obra_id"] != obra_id]
                            tags_df.to_csv("data/tags.csv", index=False)
                            st.success(f"Tags da obra '{obra_options[obra_id]}' excluídas com sucesso!")
                            st.rerun()
                    
                    elif delete_options == "Excluir todas as tags":
                        if st.button("Excluir todas as tags"):
                            confirmation = st.text_input("Digite 'CONFIRMAR' para excluir todas as tags:")
                            if confirmation == "CONFIRMAR":
                                pd.DataFrame(columns=tags_df.columns).to_csv("data/tags.csv", index=False)
                                st.success("Todos os dados de tags foram excluídos!")
                                st.rerun()
                
                st.subheader("Usuários e Respostas")
                st.dataframe(users_df)
                
                # Opção para excluir dados de usuários
                with st.expander("Excluir dados de usuários"):
                    st.warning("⚠️ Cuidado! Esta ação não pode ser desfeita.")
                    
                    if st.button("Excluir todos os dados de usuários"):
                        confirmation = st.text_input("Digite 'CONFIRMAR' para excluir todos os dados de usuários:")
                        if confirmation == "CONFIRMAR":
                            pd.DataFrame(columns=users_df.columns).to_csv("data/users.csv", index=False)
                            st.success("Todos os dados de usuários foram excluídos!")
                            st.rerun()
                
                # Opção para download dos dados
                st.download_button(
                    label="Download dados de tags (CSV)",
                    data=tags_df.to_csv(index=False).encode('utf-8'),
                    file_name='tags_data.csv',
                    mime='text/csv',
                )
                
                st.download_button(
                    label="Download dados de usuários (CSV)",
                    data=users_df.to_csv(index=False).encode('utf-8'),
                    file_name='users_data.csv',
                    mime='text/csv',
                )
        def df_to_pdf_bytes(df, title="Relatório"):
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []

            styles = getSampleStyleSheet()
            elements.append(Paragraph(title, styles["Heading1"]))
            elements.append(Spacer(1, 12))

            data = [df.columns.tolist()] + df.astype(str).values.tolist()
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ]))

            elements.append(table)
            doc.build(elements)
            pdf = buffer.getvalue()
            buffer.close()
            return pdf

        # Botões de download em PDF
        st.download_button(
            label="Download dados de tags (PDF)",
            data=df_to_pdf_bytes(tags_df, title="Relatório de Tags"),
            file_name="tags_data.pdf",
            mime="application/pdf"
        )

        st.download_button(
            label="Download dados de usuários (PDF)",
            data=df_to_pdf_bytes(users_df, title="Relatório de Usuários"),
            file_name="users_data.pdf",
            mime="application/pdf"
        )


        
        # Tab 2: Gerenciar Obras
        with admin_tabs[1]:
            st.write("### Gerenciar Obras")
            
            # Verificar se o arquivo de obras existe, caso contrário, criá-lo
            if not os.path.exists("data/obras.csv"):
                # Converter obras iniciais para CSV
                obras_iniciais = load_obras()
                obras_df = pd.DataFrame(obras_iniciais)
                obras_df.to_csv("data/obras.csv", index=False)
            else:
                obras_df = pd.read_csv("data/obras.csv")
            
            # Exibir obras existentes
            st.subheader("Obras Existentes")
            st.dataframe(obras_df[["id", "titulo", "artista", "ano"]])
            
            # Adicionar nova obra
            st.subheader("Adicionar Nova Obra")
            with st.form("adicionar_obra"):
                novo_titulo = st.text_input("Título da Obra:")
                novo_artista = st.text_input("Artista:")
                novo_ano = st.text_input("Ano:")
                
                # Opções para a imagem (URL ou upload)
                imagem_opcao = st.radio("Fonte da Imagem:", ["URL", "Upload"])
                
                if imagem_opcao == "URL":
                    imagem_url = st.text_input("URL da Imagem:")
                    imagem_path = imagem_url
                else:
                    uploaded_file = st.file_uploader("Carregar Imagem", type=["jpg", "jpeg", "png"])
                    if uploaded_file is not None:
                        # Salvar imagem carregada
                        if not os.path.exists("data/uploads"):
                            os.makedirs("data/uploads")
                        
                        img_path = f"data/uploads/{uploaded_file.name}"
                        with open(img_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        imagem_path = img_path
                        st.success(f"Imagem carregada: {uploaded_file.name}")
                    else:
                        imagem_path = ""
                
                submit_obra = st.form_submit_button("Adicionar Obra")
                
                if submit_obra:
                    if not imagem_path:
                        st.error("Preencha todos os campos obrigatórios!")
                    else:
                        # Gerar novo ID (maior ID existente + 1)
                        novo_id = 1
                        if not obras_df.empty:
                            novo_id = obras_df["id"].max() + 1
                        
                        # Adicionar nova obra
                        nova_obra = pd.DataFrame([{
                            "id": novo_id,
                            "titulo": novo_titulo,
                            "artista": novo_artista,
                            "ano": novo_ano,
                            "imagem": imagem_path
                        }])
                        
                        obras_atualizadas = pd.concat([obras_df, nova_obra], ignore_index=True)
                        obras_atualizadas.to_csv("data/obras.csv", index=False)
                        
                        # Limpar o cache para forçar o recarregamento das obras
                        st.cache_data.clear()
                        
                        st.success(f"Obra '{novo_titulo}' adicionada com sucesso!")
                        st.rerun()
            
            # Excluir obras
            st.subheader("Excluir Obra")
            with st.form("excluir_obra"):
                if not obras_df.empty:
                    obra_para_excluir = st.selectbox(
                        "Selecione a obra para excluir:",
                        [""] + [f"{row['id']}: {row['titulo']} - {row['artista']}" for _, row in obras_df.iterrows()]
                    )
                    
                    submit_exclusao = st.form_submit_button("Excluir Obra")
                    
                    if submit_exclusao and obra_para_excluir:
                        obra_id = int(obra_para_excluir.split(":")[0])
                        
                        # Verificar se há tags associadas à obra
                        tags_df = pd.read_csv("data/tags.csv")
                        tags_associadas = tags_df[tags_df["obra_id"] == obra_id]
                        
                        if not tags_associadas.empty:
                            st.warning(f"Esta obra possui {len(tags_associadas)} tags associadas. Exclua as tags primeiro.")
                        else:
                            # Excluir obra
                            obras_df = obras_df[obras_df["id"] != obra_id]
                            obras_df.to_csv("data/obras.csv", index=False)
                            
                            # Limpar o cache para forçar o recarregamento das obras
                            st.cache_data.clear()
                            
                            st.success("Obra excluída com sucesso!")
                            st.rerun()
                else:
                    st.write("Não há obras para excluir.")
        
        # Tab 3: Gerenciar Administradores
        with admin_tabs[2]:
            st.subheader("Gerenciar Administradores")
            
            with st.expander("Adicionar novo administrador"):
                with st.form("add_admin_form"):
                    new_username = st.text_input("Novo usuário:")
                    new_password = st.text_input("Nova senha:", type="password")
                    confirm_password = st.text_input("Confirmar senha:", type="password")
                    
                    submit_admin = st.form_submit_button("Adicionar Administrador")
                    
                    if submit_admin:
                        if new_password != confirm_password:
                            st.error("As senhas não coincidem!")
                        else:
                            # Carregar admins existentes
                            admin_df = pd.read_csv("data/admin.csv")
                            
                            # Verificar se o nome de usuário já existe
                            if new_username in admin_df["username"].values:
                                st.error(f"O usuário '{new_username}' já existe!")
                            else:
                                # Adicionar novo admin
                                hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
                                new_admin = pd.DataFrame([{
                                    "username": new_username,
                                    "password": hashed_password
                                }])
                                updated_df = pd.concat([admin_df, new_admin], ignore_index=True)
                                updated_df.to_csv("data/admin.csv", index=False)
                                st.success(f"Administrador '{new_username}' adicionado com sucesso!")
            
            # Exibir lista de administradores existentes
            admin_df = pd.read_csv("data/admin.csv")
            st.write("### Administradores existentes:")
            st.dataframe(admin_df[["username"]])  # Mostrar apenas nomes de usuário, não senhas
            
            # Excluir administrador
            with st.expander("Excluir administrador"):
                admin_para_excluir = st.selectbox(
                    "Selecione o administrador para excluir:",
                    [""] + list(admin_df["username"].values)
                )
                
                if admin_para_excluir and st.button("Excluir Administrador"):
                    # Verificar se é o último administrador
                    if len(admin_df) <= 1:
                        st.error("Não é possível excluir o último administrador!")
                    else:
                        admin_df = admin_df[admin_df["username"] != admin_para_excluir]
                        admin_df.to_csv("data/admin.csv", index=False)
                        st.success(f"Administrador '{admin_para_excluir}' excluído com sucesso!")
                        st.rerun()
        
        # Botão para logout (no final da página)
        st.write("---")
        if st.button("Logout"):
            st.session_state['admin_logged_in'] = False
            st.rerun()

# Executar o aplicativo
if __name__ == "__main__":
    main()
