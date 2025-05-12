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
from supabase import create_client
import uuid

# Configuração do Supabase
SUPABASE_URL = "https://irxyfzfvvdszfkkjothq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlyeHlmemZ2dmRzemZra2pvdGhxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY5MjE2NzMsImV4cCI6MjA2MjQ5NzY3M30.vcEG3PUVG_X_PdML_JHqygAjcumfvrcAAteEYF5msHo"
# Inicializar cliente Supabase
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configuração inicial do Streamlit
st.set_page_config(page_title="Projeto Folksonomia", layout="wide")

# Funções para interagir com o Supabase
def check_and_init_admin():
    try:
        # Verificar se há algum admin, caso contrário criar um padrão
        response = supabase_client.table('admin').select('*').execute()
        if not response.data:
            hashed_password = hashlib.sha256("admin123".encode()).hexdigest()
            # Remover id da inserção - correção para erro de identidade
            supabase_client.table('admin').insert({
                "username": "admin",
                "password": hashed_password
            }).execute()
    except Exception as e:
        st.error(f"Erro ao verificar admin: {e}")

# Função para fazer upload de imagem para o Supabase Storage
def upload_image_to_storage(file):
    try:
        # Gerar um nome único para o arquivo
        file_ext = file.name.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        
        # Fazer upload do arquivo para o bucket já criado manualmente
        supabase_client.storage.from_('obras-imagens').upload(
            unique_filename,
            file.getvalue()
        )
        
        # Obter a URL pública da imagem
        image_url = supabase_client.storage.from_('obras-imagens').get_public_url(unique_filename)
        
        return image_url
    except Exception as e:
        st.error(f"Erro detalhado: {str(e)}")
        return None



# Chamar a verificação do admin ao iniciar
try:
    check_and_init_admin()
except Exception as e:
    st.error(f"Erro ao verificar admin: {e}")

# Carregar dados das obras
@st.cache_data(ttl=5, show_spinner=False) # Expira o cache após 5 segundos
def load_obras():
    try:
        response = supabase_client.table('obras').select('*').execute()
        if response.data:
            return response.data
        else:
            # Dados iniciais se a tabela estiver vazia
            obras = [
                {"id": 1, "titulo": "Guernica", "artista": "Pablo Picasso", "ano": "1937",
                 "imagem": "https://upload.wikimedia.org/wikipedia/en/7/74/PicassoGuernica.jpg"},
            ]
            # Inserir obra inicial
            supabase_client.table('obras').insert(obras).execute()
            return obras
    except Exception as e:
        st.error(f"Erro ao carregar obras: {e}")
        return []

# Funções utilitárias
def generate_user_id():
    """Gera um ID único para o usuário"""
    return base64.b64encode(os.urandom(12)).decode('ascii')

def save_user_answers(user_id, answers):
    """Salva as respostas do questionário no Supabase"""
    try:
        new_row = {
            "user_id": user_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "q1": answers["q1"],
            "q2": answers["q2"],
            "q3": answers["q3"]
        }
        supabase_client.table('users').insert(new_row).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar respostas: {e}")
        return False

def save_tag(user_id, obra_id, tag):
    """Salva uma tag associada a uma obra no Supabase"""
    try:
        new_row = {
            "user_id": user_id,
            "obra_id": obra_id,
            "tag": tag.lower().strip(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        supabase_client.table('tags').insert(new_row).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar tag: {e}")
        return False

def get_tags_for_obra(obra_id):
    """Obtém todas as tags para uma obra específica do Supabase"""
    try:
        response = supabase_client.table('tags').select('tag').eq('obra_id', obra_id).execute()
        if response.data:
            # Converter para DataFrame e contar ocorrências
            tags_df = pd.DataFrame(response.data)
            tag_counts = tags_df['tag'].value_counts().reset_index()
            tag_counts.columns = ["tag", "count"]
            return tag_counts
        return pd.DataFrame(columns=["tag", "count"])
    except Exception as e:
        st.error(f"Erro ao obter tags: {e}")
        return pd.DataFrame(columns=["tag", "count"])

def check_admin_credentials(username, password):
    """Verifica as credenciais do administrador no Supabase"""
    try:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        response = supabase_client.table('admin').select('*')\
            .eq('username', username)\
            .eq('password', hashed_password)\
            .execute()
        return len(response.data) > 0
    except Exception as e:
        st.error(f"Erro ao verificar credenciais: {e}")
        return False

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
            st.write(f"**{obra['titulo']}**")
            st.write(f"{obra['artista']}, {obra['ano']}")
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

                # Exibir tags populares para esta obra
                tags = get_tags_for_obra(obra['id'])
                if not tags.empty:
                    st.write("**Tags populares:**")
                    for _, row in tags.head(5).iterrows():
                        st.write(f"- {row['tag']} ({row['count']} vezes)")
                else:
                    st.write("Ainda não há tags para esta obra. Seja o primeiro a adicionar!")

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
            # Carregar dados do Supabase
            try:
                tags_response = supabase_client.table('tags').select('*').execute()
                users_response = supabase_client.table('users').select('*').execute()
                if tags_response.data:
                    tags_df = pd.DataFrame(tags_response.data)
                else:
                    tags_df = pd.DataFrame(columns=["user_id", "obra_id", "tag", "timestamp"])
                if users_response.data:
                    users_df = pd.DataFrame(users_response.data)
                else:
                    users_df = pd.DataFrame(columns=["user_id", "timestamp", "q1", "q2", "q3"])

                # Métricas principais
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total de Usuários", len(users_df["user_id"].unique()) if not users_df.empty else 0)
                with col2:
                    st.metric("Total de Tags", len(tags_df) if not tags_df.empty else 0)
                with col3:
                    st.metric("Tags Únicas", len(tags_df["tag"].unique()) if not tags_df.empty else 0)

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
                            if not tags_df.empty:
                                tag_to_delete = st.selectbox("Selecione a tag:", [""] + list(tags_df["tag"].unique()))
                                if tag_to_delete and st.button("Excluir tag selecionada"):
                                    supabase_client.table('tags').delete().eq('tag', tag_to_delete).execute()
                                    st.success(f"Tag '{tag_to_delete}' excluída com sucesso!")
                                    st.rerun()
                            else:
                                st.write("Não há tags para excluir.")
                        elif delete_options == "Excluir todas as tags de uma obra":
                            obras = load_obras()
                            if obras:
                                obra_options = {obra["id"]: f"{obra['titulo']} - {obra['artista']}" for obra in obras}
                                obra_to_delete = st.selectbox(
                                    "Selecione a obra:",
                                    [""] + [f"{id}: {title}" for id, title in obra_options.items()]
                                )
                                if obra_to_delete and st.button("Excluir tags da obra selecionada"):
                                    obra_id = int(obra_to_delete.split(":")[0])
                                    supabase_client.table('tags').delete().eq('obra_id', obra_id).execute()
                                    st.success(f"Tags da obra '{obra_options[obra_id]}' excluídas com sucesso!")
                                    st.rerun()
                            else:
                                st.write("Não há obras cadastradas.")
                        elif delete_options == "Excluir todas as tags":
                            if st.button("Excluir todas as tags"):
                                confirmation = st.text_input("Digite 'CONFIRMAR' para excluir todas as tags:")
                                if confirmation == "CONFIRMAR":
                                    supabase_client.table('tags').delete().neq('user_id', 'dummy_value').execute()
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
                                supabase_client.table('users').delete().neq('user_id', 'dummy_value').execute()
                                st.success("Todos os dados de usuários foram excluídos!")
                                st.rerun()

                    # Opção para download dos dados
                    if not tags_df.empty:
                        st.download_button(
                            label="Download dados de tags (CSV)",
                            data=tags_df.to_csv(index=False).encode('utf-8'),
                            file_name='tags_data.csv',
                            mime='text/csv',
                        )
                    if not users_df.empty:
                        st.download_button(
                            label="Download dados de usuários (CSV)",
                            data=users_df.to_csv(index=False).encode('utf-8'),
                            file_name='users_data.csv',
                            mime='text/csv',
                        )
            except Exception as e:
                st.error(f"Erro ao carregar dados para análise: {e}")

        def df_to_pdf_bytes(df, title="Relatório"):
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            elements.append(Paragraph(title, styles["Heading1"]))
            elements.append(Spacer(1, 12))
            if not df.empty:
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
            else:
                elements.append(Paragraph("Não há dados disponíveis", styles["Normal"]))
            doc.build(elements)
            pdf = buffer.getvalue()
            buffer.close()
            return pdf

        # Botões de download em PDF
        try:
            tags_response = supabase_client.table('tags').select('*').execute()
            users_response = supabase_client.table('users').select('*').execute()
            if tags_response.data:
                tags_df = pd.DataFrame(tags_response.data)
                st.download_button(
                    label="Download dados de tags (PDF)",
                    data=df_to_pdf_bytes(tags_df, title="Relatório de Tags"),
                    file_name="tags_data.pdf",
                    mime="application/pdf"
                )
            if users_response.data:
                users_df = pd.DataFrame(users_response.data)
                st.download_button(
                    label="Download dados de usuários (PDF)",
                    data=df_to_pdf_bytes(users_df, title="Relatório de Usuários"),
                    file_name="users_data.pdf",
                    mime="application/pdf"
                )
        except Exception as e:
            st.error(f"Erro ao preparar downloads: {e}")

        # Tab 2: Gerenciar Obras
        with admin_tabs[1]:
            st.write("### Gerenciar Obras")
            # Exibir obras existentes
            obras = load_obras()
            if obras:
                obras_df = pd.DataFrame(obras)
                st.subheader("Obras Existentes")
                st.dataframe(obras_df[["id", "titulo", "artista", "ano"]])
            else:
                st.write("Não há obras cadastradas.")

            # Adicionar nova obra
            st.subheader("Adicionar Nova Obra")
            with st.form("adicionar_obra"):
                novo_titulo = st.text_input("Título da Obra:")
                novo_artista = st.text_input("Artista:")
                novo_ano = st.text_input("Ano:")
                
                # Opções para a imagem (URL ou upload)
                imagem_opcao = st.radio("Fonte da Imagem:", ["URL", "Upload"])
                
                imagem_path = ""
                if imagem_opcao == "URL":
                    imagem_path = st.text_input("URL da Imagem:")
                else:
                    uploaded_file = st.file_uploader("Carregar Imagem", type=["jpg", "jpeg", "png"])
                
                submit_obra = st.form_submit_button("Adicionar Obra")
                
                if submit_obra:
                    if not novo_titulo or not novo_artista:
                        st.error("Preencha o título e o artista!")
                    elif imagem_opcao == "URL" and not imagem_path:
                        st.error("Informe a URL da imagem!")
                    elif imagem_opcao == "Upload" and uploaded_file is None:
                        st.error("Faça o upload de uma imagem!")
                    else:
                        # Se foi escolhido upload, processar o arquivo
                        if imagem_opcao == "Upload" and uploaded_file is not None:
                            # Fazer upload da imagem para o Storage do Supabase
                            with st.spinner("Fazendo upload da imagem..."):
                                imagem_path = upload_image_to_storage(uploaded_file)
                                if not imagem_path:
                                    st.error("Falha ao fazer upload da imagem.")
                                    st.stop()
                        
                        # Gerar novo ID (maior ID existente + 1)
                        novo_id = 1
                        if obras:
                            ids = [obra["id"] for obra in obras]
                            novo_id = max(ids) + 1
                        
                        # Adicionar nova obra
                        try:
                            nova_obra = {
                                "id": novo_id,
                                "titulo": novo_titulo,
                                "artista": novo_artista,
                                "ano": novo_ano,
                                "imagem": imagem_path
                            }
                            supabase_client.table('obras').insert(nova_obra).execute()
                            # Limpar o cache para forçar o recarregamento das obras
                            st.cache_data.clear()
                            st.success(f"Obra '{novo_titulo}' adicionada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao adicionar obra: {e}")

            # Excluir obras
            st.subheader("Excluir Obra")
            with st.form("excluir_obra"):
                if obras:
                    obra_para_excluir = st.selectbox(
                        "Selecione a obra para excluir:",
                        [""] + [f"{obra['id']}: {obra['titulo']} - {obra['artista']}" for obra in obras]
                    )
                    submit_exclusao = st.form_submit_button("Excluir Obra")
                    if submit_exclusao and obra_para_excluir:
                        try:
                            obra_id = int(obra_para_excluir.split(":")[0])
                            # Verificar se há tags associadas à obra
                            tags_response = supabase_client.table('tags').select('*').eq('obra_id', obra_id).execute()
                            if tags_response.data:
                                st.warning(f"Esta obra possui {len(tags_response.data)} tags associadas. Exclua as tags primeiro.")
                            else:
                                # Excluir obra
                                supabase_client.table('obras').delete().eq('id', obra_id).execute()
                                # Limpar o cache para forçar o recarregamento das obras
                                st.cache_data.clear()
                                st.success("Obra excluída com sucesso!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao excluir obra: {e}")
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
                            try:
                                # Verificar se o nome de usuário já existe
                                admin_response = supabase_client.table('admin').select('*').eq('username', new_username).execute()
                                if admin_response.data:
                                    st.error(f"O usuário '{new_username}' já existe!")
                                else:
                                    # Adicionar novo admin - sem ID (coluna de identidade)
                                    hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
                                    supabase_client.table('admin').insert({
                                        "username": new_username,
                                        "password": hashed_password
                                    }).execute()
                                    st.success(f"Administrador '{new_username}' adicionado com sucesso!")
                            except Exception as e:
                                st.error(f"Erro ao adicionar administrador: {e}")

            # Exibir lista de administradores existentes
            try:
                admin_response = supabase_client.table('admin').select('*').execute()
                if admin_response.data:
                    admin_df = pd.DataFrame(admin_response.data)
                    st.write("### Administradores existentes:")
                    st.dataframe(admin_df[["username"]]) # Mostrar apenas nomes de usuário, não senhas

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
                                try:
                                    supabase_client.table('admin').delete().eq('username', admin_para_excluir).execute()
                                    st.success(f"Administrador '{admin_para_excluir}' excluído com sucesso!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir administrador: {e}")
                else:
                    st.warning("Nenhum administrador encontrado.")
            except Exception as e:
                st.error(f"Erro ao carregar administradores: {e}")

        # Botão para logout
        st.write("---")
        if st.button("Logout"):
            st.session_state['admin_logged_in'] = False
            st.rerun()

# Executar o aplicativo
if __name__ == "__main__":
    main()
