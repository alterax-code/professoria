# Professoria

Un professeur particulier dans Claude Code. Tu donnes un sujet, il construit un programme, puis il enchaine cours, exercices et evaluations en s'adaptant a ton niveau.

```
/prof statistiques
```

## Ce qu'il fait

- **Au premier lancement** : il te pose quelques questions (niveau, objectif, temps dispo), construit un programme complet du sujet, puis te fait passer un petit test pour savoir ou tu en es.
- **Ensuite, en boucle** : cours, puis exercices, puis evaluation.
- **Il s'adapte** : il insiste sur ce que tu rates, change d'angle si tu bloques, monte la difficulte quand tu reussis.
- **Il te fait reviser** : de petits rappels sur ce que tu maitrises deja, de plus en plus espaces (1, 3, 7, 14, 30 puis 60 jours).
- **Il se fait relire** : chaque cours, exercice et evaluation est verifie par un second agent independant avant de t'etre montre, pour eviter les erreurs.
- **Il se souvient** : ta progression est sauvegardee, tu reprends ou tu t'es arrete, meme des jours plus tard.

## Installation

Prerequis : [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) et Python 3.

Dans Claude Code :

```
/plugin marketplace add alterax-code/professoria
/plugin install professoria@professoria
```

Redemarre Claude Code, c'est pret.

## Mises a jour

Chaque commit publie sur ce depot est une nouvelle version.

**Automatiques (recommande, a faire une seule fois)** : tape `/plugin`, va dans **Marketplaces**, choisis `professoria`, puis **Enable auto-update**. Les mises a jour arrivent ensuite toutes seules en arriere-plan ; quand Claude Code te le signale, lance `/reload-plugins` ou redemarre.

**Manuelles** :

```
/plugin marketplace update professoria
```

Puis `/reload-plugins`, ou redemarre Claude Code.

## Utilisation

| Commande | Effet |
|---|---|
| `/prof statistiques` | Commence un nouveau sujet, ou reprend un sujet existant |
| `/prof liste` | Affiche tes sujets en cours |
| `/prof bilan statistiques` | Affiche ta progression sur un sujet |

Pendant une session, tu peux dire : `stop`, `plus facile`, `plus dur`, `indice`, `bilan`.

Si la commande `/prof` entre en conflit avec un autre plugin, utilise `/professoria:prof`.

## Ou sont mes donnees

Tout est stocke en local dans `~/.professoria/<sujet>/` :

- `curriculum.json` : le programme du sujet
- `learner.json` : ta progression (maitrise par notion, erreurs, dates de revision)
- `contenu/` : les cours et exercices deja valides

Pour recommencer un sujet de zero, supprime son dossier.

Pour stocker les donnees ailleurs, definis la variable d'environnement `PROFESSORIA_HOME`.

## Contenu du plugin

```
.claude-plugin/       manifeste du plugin
commands/prof.md      la commande /prof
skills/professoria/   le protocole du prof et le script de suivi
agents/               l'agent verificateur
```

## Auteur

Alterax
