from flask import Flask, render_template, request, jsonify, send_file,flash,get_flashed_messages,redirect,url_for,session
import yt_dlp
from moviepy.editor import VideoFileClip
import os
import uuid
import tempfile
import shutil
import queue
import threading
import time
import re  # Para validação de caracteres
from firebase_admin import credentials, auth, initialize_app

from firebase_config import initialize_firebase 


app = Flask(__name__)


# Dicionário para armazenar as tarefas de download ativas
downloads_ativos = {}



# Inicializando o Firebase Admin SDK
initialize_firebase()

@app.before_request
def check_login_status():
    """Verifica se o usuário está autenticado antes de acessar as rotas privadas"""
    if 'uid' in session:
        try:
            user = auth.get_user(session['uid'])  # Verifica a existência do usuário
        except auth.UserNotFoundError:
            session.clear()  # Limpa sessão se o usuário não for encontrado
            return redirect(url_for('/'))  # Redireciona para a página de login


@app.route('/dashboard')
def dashboard():
    if 'uid' not in session:
        return redirect(url_for('login'))  # Se não estiver logado, redireciona para login
    return render_template('/')  # Se estiver logado, renderiza o dashboard

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            # Criar um novo usuário no Firebase
            user = auth.create_user(email=email, password=password)
            flash('Usuário cadastrado com sucesso!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Erro: {e}', 'error')
    return render_template('register.html')




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            # Realizar login usando Firebase Auth
            user = auth.get_user_by_email(email)
            session['uid'] = user.uid
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('/'))  # Ou para 'index', conforme sua rota
        except Exception as e:
            flash(f'Erro: {e}', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('uid', None)  # Remove o UID da sessão
    
    session.clear()  # Limpar todos os dados da sessão
    return redirect(url_for('/'))













# Função para limpar o diretório temporário após o tempo especificado
def limpar_diretorio_temp(diretorio_temp, delay=60):
    # Espera o tempo definido antes de tentar limpar
    time.sleep(delay)
    print(f"Limpando diretório temporário {diretorio_temp}...")

    try:
        # Verifica se o diretório ainda existe e o remove com todo o conteúdo
        if os.path.exists(diretorio_temp):
            shutil.rmtree(diretorio_temp)
            print(f"Diretório {diretorio_temp} removido com sucesso.")
    except Exception as e:
        print(f"Erro ao remover o diretório {diretorio_temp}: {e}")
# Função para obter a duração do vídeo
def get_video_duration(video_url):
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0',
        },
        'cookiefile': 'cookies.txt',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)
        return int(info_dict.get('duration', 0))  # Duração em segundos


# Fila de downloads
download_queue = queue.Queue()

# Função para processar a fila de downloads
def download_worker():
    while True:
        video_url, start_time, end_time, selected_resolution, response_queue = download_queue.get()
        try:
            process_download(video_url, start_time, end_time, selected_resolution, response_queue)
        finally:
            download_queue.task_done()

# Função para processar o download
def process_download(video_url, start_time, end_time, selected_resolution, response_queue):
   
    download_id = str(uuid.uuid4())  # Cria um ID único para o download
    downloads_ativos[video_url] = download_id  # Registra o download como ativo
    # Criar um diretório temporário único para este download
    temp_dir = tempfile.mkdtemp()
    downloaded_video_path = os.path.join(temp_dir, "downloaded_video.mp4")
    output_path = os.path.join(temp_dir, f"cut_video_{uuid.uuid4()}.mp4")
    


    ydl_opts = {
        'format': f'{selected_resolution}+bestaudio/best',
        'outtmpl': os.path.join(temp_dir, "downloaded_video.%(ext)s"),  # Usar um template no diretório temporário
        'noplaylist': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0'
        },
        'cookiefile':'cookies.txt' ,
    }

    try:
         
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Verifique se o download foi cancelado após cada parte do download
            ydl.add_progress_hook(lambda d: check_download_cancelation(d, video_url, download_id, response_queue))
            ydl.download([video_url])

        # Verifica se o download foi cancelado após o download
        if downloads_ativos.get(video_url) != download_id:
            response_queue.put("Download cancelado pelo usuário.")
            return

        # Verificar os arquivos baixados
        downloaded_files = [f for f in os.listdir(temp_dir) if f.startswith("downloaded_video.")]
        if not downloaded_files:
            response_queue.put(f"Erro: O vídeo não foi baixado corretamente.")
            return

        # Encontrar o arquivo baixado
        for downloaded_file in downloaded_files:
            downloaded_file_path = os.path.join(temp_dir, downloaded_file)

            # Cortar o vídeo
            with VideoFileClip(downloaded_file_path) as video:
                cut_video = video.subclip(start_time, end_time)
                cut_video.write_videofile(output_path)

            # Verificar se o vídeo cortado foi criado corretamente
            if not os.path.exists(output_path):
                response_queue.put(f"Erro: O vídeo processado {output_path} não foi criado corretamente.")
                return

            # Se o vídeo cortado foi criado corretamente, enviar o caminho
            response_queue.put((output_path,))
            return  # Termina após o primeiro arquivo encontrado e processado
       

    except Exception as e:
        response_queue.put(f"Erro ao processar o vídeo: {str(e)}")
    finally:
        # Remove a tarefa ativa após completar ou falhar
        downloads_ativos.pop(video_url, None)
        try:
            # Limpar arquivos temporários
            shutil.rmtree(temp_dir)  # Remove o diretório temporário inteiro
        except Exception as cleanup_error:
            print(f"Erro ao limpar os arquivos temporários: {str(cleanup_error)}")

def check_download_cancelation(d, video_url, download_id, response_queue):
    if d['status'] == 'downloading':
        # Verifica se o download foi cancelado
        if downloads_ativos.get(video_url) != download_id:
            response_queue.put("Download cancelado pelo usuário.")
            # Pode levantar uma exceção para interromper o download, se necessário
            raise Exception("Download cancelado.")
# Rota para cancelar o download
@app.route('/cancel_download', methods=['POST'])
def cancel_download():
    app.logger.info("Cancelamento de download recebido.")
    data = request.json
    video_url = data.get('url')

    if video_url in downloads_ativos:
        downloads_ativos.pop(video_url, None)  # Remove o download ativo
        return jsonify({'success': True, 'message': 'Download cancelado com sucesso.'})
    else:
        return jsonify({'success': False, 'message': 'Nenhum download ativo para esta URL.'})



# Inicializa a thread de download
threading.Thread(target=download_worker, daemon=True).start()

@app.route('/', methods=['GET', 'POST'])
def index():
    
    return render_template('index.html')

@app.route('/fetch_video_info', methods=['POST'])
def fetch_video_info():
    video_url = request.json['url']
    try:
        ydl_opts = {
            'format': 'best',
            'noplaylist': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0',
            },
            'cookiefile': 'cookies.txt',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=False)
            thumbnail_url = info_dict.get('thumbnail', None)
            formats = info_dict.get('formats', [])
            allowed_resolutions = {144,240,360, 480}
            unique_formats = {}
            seen_resolutions = set()
            

            for fmt in formats:
                height = fmt.get('height')
                if height in allowed_resolutions:
                    if height not in seen_resolutions:
                        seen_resolutions.add(height)
                        unique_formats[fmt['format_id']] = fmt
            
            

            return jsonify({
                'thumbnail_url': thumbnail_url,
                'formats': list(unique_formats.values())
            })
    except Exception as e:
        return render_template('error.html', error_code=500, error_message=f"Erro ao buscar informações do vídeo: {str(e)}"), 500
        
        

@app.route('/download', methods=['POST'])
def download():
    video_url = request.form.get('url')
    if not video_url:
        return render_template('error.html', error_code=400, error_message="Erro: A URL do vídeo não pode estar vazia."), 400
    
    start_time = request.form['start_time']  # Aqui, ainda é uma string
    end_time = request.form['end_time']      # Aqui, ainda é uma string
    selected_resolution = request.form['resolution']
      # Limitar a duração do vídeo que pode ser cortada
    max_video_duration = 10 * 60  # 10 minutos em segundos
    


   

   # Função para converter o tempo em segundos
    def convert_to_seconds(time_str):
        # Verifica se o tempo está em formato "MM:SS"
        if ':' in time_str:
            minutes, seconds = map(int, time_str.split(':'))
            return minutes * 60 + seconds
        else:
            # Se não houver ":", assume que está em segundos
            return int(time_str)
        
     # Função para validar caracteres especiais   
    def validate_time_input(time_str):
        if not re.match(r'^\d{1,2}:\d{2}$', time_str) and not re.match(r'^\d+$', time_str):
            raise ValueError("Formato de tempo inválido. Use 'MM:SS' ou 'SS'.")    

    # Converte os tempos de "MM:SS" ou "SS" para segundos
    try:
        validate_time_input(start_time)
        validate_time_input(end_time)
        start_time_seconds = convert_to_seconds(start_time)
        end_time_seconds = convert_to_seconds(end_time)

        # Valida os tempos
        if start_time_seconds < 0 or end_time_seconds < 0:
            return render_template('error.html', error_code=400, error_message="Erro: Os tempos não podem ser negativos."), 400

       
        if start_time_seconds >= end_time_seconds:
            return render_template('error.html', error_code=400, error_message="Erro: Os tempos não podem ser negativos."), 400
        
        video_duration = get_video_duration(video_url)
         # Verifica se o vídeo completo é maior que 10 minutos
        
        
        if video_duration > max_video_duration:
            return render_template('error.html', error_code=400, error_message="Erro: O vídeo completo não pode exceder 10 minutos."), 400
       
       
        if start_time_seconds > video_duration or end_time_seconds > video_duration:
            return render_template('error.html', error_code=400, error_message="Erro: Os tempos não podem ser negativos."), 400
       
        
        
        

    except ValueError:
        return render_template('error.html', error_code=400, error_message="Erro: Os tempos não podem ser negativos."), 400
    except Exception as e:
        return render_template('error.html', error_code=500, error_message=f"Erro inesperado ao processar os tempos: {str(e)}"), 500

    # Fila de resposta para retornar o resultado do download
    response_queue = queue.Queue()
    
    # Adiciona a tarefa à fila
    download_queue.put((video_url, start_time, end_time, selected_resolution, response_queue))

    
    # Aguardando a resposta do download
    response = response_queue.get()  # Isso vai bloquear até que o download esteja completo

    # Se a resposta for um caminho de arquivo, envie o arquivo para download
    if isinstance(response, tuple):
        
        try:
            return send_file(response[0], as_attachment=True)
        finally:
            # Inicia uma thread para limpar o diretório temporário após 60 segundos
            diretorio_temp = os.path.dirname(response[0])
            threading.Thread(target=limpar_diretorio_temp, args=(diretorio_temp,)).start()
    

    return render_template('error.html', error_code=500, error_message=response), 500
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_code=500, error_message="Erro interno do servidor."), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)











































