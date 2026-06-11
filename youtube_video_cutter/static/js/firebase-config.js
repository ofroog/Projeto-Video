// firebase-config.js

// Configuração do Firebase
const firebaseConfig = {
    apiKey: "AIzaSyB3UwInUDAOAlIfLF67_9_iLUrcMC8_Jx0",
    authDomain: "corterapidos-86d97.firebaseapp.com",
    projectId: "corterapidos-86d97",
    storageBucket: "corterapidos-86d97.firebasestorage.app",
    messagingSenderId: "1049483362891",
    appId: "1:1049483362891:web:0f2980a6ce3b4b331443ce",
    measurementId: "G-8CHG0JWYW9"
};

// Inicializa o Firebase
firebase.initializeApp(firebaseConfig);

// Obter referência para autenticação
const auth = firebase.auth();
console.log(firebase.apps.length ? "Firebase conectado" : "Firebase não está conectado");


