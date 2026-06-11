import firebase_admin
from firebase_admin import credentials, auth, firestore

def initialize_firebase():

    # Inicializa o Firebase com a chave do seu serviço
 cred = credentials.Certificate('C:/Users/ro_dr/Desktop/atualizados/favicons/corterapidos-86d97-firebase-adminsdk-lew2s-460043b620.json')
 firebase_admin.initialize_app(cred)

# Obtenha uma instância do Firestore
 db = firestore.client()

# Agora você pode usar o Firebase Auth e o Firestore no seu projeto



