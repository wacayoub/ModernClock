# ModernClock

Horloge permanente pour Enigma2, intégrée aux réglages **Date et heure**. La version 1.4.0 affiche à droite un aperçu qui suit les changements de police, de style, de couleur, de taille et d’opacité. Le bouton bleu permet de placer l’horloge à sa taille réelle sur la TV.

## Installation

Téléchargez l’[archive d’installation de la version 1.4.0](https://github.com/wacayoub/ModernClock/releases/tag/v1.4.0). Elle contient les ressources graphiques nécessaires et le guide `INTEGRATION.txt`. La release fournit également la somme SHA-256 de l’archive.

L’intégration a été testée sur OpenATV 8.0.1. Sur le récepteur, décompressez l’archive et lancez `python3 install_native.py inspect` pour vérifier la structure de votre image avant l’installation. L’installateur sauvegarde les fichiers système qu’il modifie.

Pour mettre à niveau une installation native existante, utilisez `python3 upgrade_presentation.py inspect`, puis `python3 upgrade_presentation.py install` si la vérification réussit. Redémarrez ensuite l’interface Enigma2.

Code sous licence [MIT](LICENSE).
