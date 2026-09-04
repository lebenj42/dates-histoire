# Dates d'Histoire — carrousel quotidien 100 % automatique

Chaque matin à 7 h (heure de Paris), sans ordinateur allumé :

1. récupération des événements survenus dans le monde à cette date (Wikipédia FR) ;
2. classement par notoriété réelle (vues mensuelles des articles) et par diversité d'époques ;
3. rédaction du titre et du résumé de chaque événement ;
4. recherche d'une **photo libre de droit** pour chacun, avec sa licence et son crédit ;
5. fabrication d'un carrousel de 8 slides 1080 × 1350 ;
6. publication sur Instagram via l'API officielle, légende et hashtags compris.

Coût : 0 €. Tout tourne sur GitHub Actions (2 000 minutes gratuites par mois, le job en
consomme environ 2 par jour).

---

## 1. Le dépôt

```bash
gh repo create dates-histoire --public --source=. --push
```

Le dépôt doit être **public** : les images sont servies depuis `raw.githubusercontent.com`,
et l'API Instagram exige des URL accessibles publiquement. Rien de sensible n'y est stocké,
les identifiants vivent dans les secrets GitHub.

## 2. Le compte Instagram

- passer le compte en **professionnel** (Créateur ou Entreprise) dans les réglages Instagram ;
- sur [developers.facebook.com](https://developers.facebook.com/apps) : créer une app,
  produit **Instagram → API setup with Instagram login** ;
- ajouter le compte comme testeur, générer un **jeton d'accès** (permissions
  `instagram_business_basic` et `instagram_business_content_publish`) ;
- récupérer l'**identifiant du compte** (`IG_USER_ID`) affiché dans la même page.

## 3. Les secrets GitHub

`Settings → Secrets and variables → Actions` :

| Secret | Obligatoire | Rôle |
|---|---|---|
| `IG_USER_ID` | oui | identifiant du compte Instagram professionnel |
| `IG_ACCESS_TOKEN` | oui | jeton longue durée (60 jours, renouvelé automatiquement) |
| `CONTACT_EMAIL` | recommandé | exigé par les règles d'usage des API Wikimedia |
| `GH_PAT` | facultatif | jeton GitHub (droit `secrets: write`) pour que le renouvellement du jeton s'écrive tout seul |
| `ANTHROPIC_API_KEY` | facultatif | fait réécrire titres et résumés par Claude au lieu des règles automatiques |

## 4. Premier essai

Onglet **Actions → Carrousel du jour → Run workflow**, en laissant `essai` sur `true` :
le carrousel est fabriqué et déposé dans `docs/AAAA-MM-JJ/`, sans rien publier.
Regarde les 8 images, puis relance avec `essai = false` pour publier pour de vrai.

Ensuite, plus rien à faire : le cron publie chaque matin.

En local :

```bash
pip install -r requirements.txt
python run.py generer                      # carrousel du jour dans docs/
python run.py generer --date 1969-07-20    # n'importe quelle date
python run.py publier --base-url https://raw.githubusercontent.com/moi/dates-histoire/main/docs --essai
```

---

## Droits sur les photos

Le pipeline ne retient qu'une image dont il peut prouver la licence :

1. **Wikimedia Commons** — n'héberge que des fichiers libres, réutilisables commercialement
   et modifiables. Les fichiers « fair use » locaux à fr.wikipedia sont explicitement écartés.
2. **Openverse**, limité à `cc0`, `pdm` (domaine public) et `by`.
   Les licences **ND** (recadrage et incrustation de texte interdits) et **SA** (obligerait à
   repartager le carrousel sous la même licence) sont exclues volontairement.
3. Si rien de propre n'est trouvé : la slide bascule sur un fond typographique, sans photo.
   Le carrousel n'est jamais bloqué et ne publie jamais une image au statut incertain.

Auteur, licence et source sont écrits en bas de chaque slide **et** repris en légende.
Une image sous CC BY exige cette mention : ne la retire pas.

## Réglages — `config.yaml`

Nom et handle de la page, nombre d'événements, longueur des titres et résumés, couleurs,
polices, heure de publication, hashtags. Le design vit dans `src/rendu.py`
(fond `#0B0B0F`, accent or `#C9A227`, Playfair Display + Inter).

## Structure

```
run.py                 generer / publier
config.yaml            tous les réglages éditoriaux et graphiques
src/wiki.py            événements du jour + classement par notoriété
src/texte.py           titres et résumés (règles, ou Claude si clé fournie)
src/images.py          photos libres de droit + licences
src/rendu.py           slides 1080x1350
src/legende.py         légende, crédits, hashtags
src/instagram.py       API de publication (carrousel)
src/etat.py            mémoire des événements déjà publiés
src/archive.py         docs/index.html, l'archive consultable
docs/AAAA-MM-JJ/       slides + manifest.json de chaque jour
```

## Limites connues

- Instagram plafonne à 25 publications par 24 h : sans objet ici, mais bon à savoir.
- Le jeton expire au bout de 60 jours ; le workflow mensuel le prolonge. Sans `GH_PAT`,
  il faut recopier le nouveau jeton à la main dans les secrets.
- Wikipédia FR ne propose pas 6 événements majeurs tous les jours de l'année ;
  le classement complète alors avec des faits moins connus plutôt que de sauter un jour.
- Le résumé automatique reprend les premières phrases de l'article. Avec
  `ANTHROPIC_API_KEY`, la rédaction est nettement meilleure — pour quelques centimes par mois.
