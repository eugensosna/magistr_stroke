// Multibranch Pipeline: Jenkins збирає кожну змінену гілку і кожен pull request.
// Результати публікуються на сервер у папку за датою збірки:
//   main          -> <DEPLOY_DIR>/20261102/
//   гілка feature -> <DEPLOY_DIR>/20261102/feature/
//   PR №7         -> <DEPLOY_DIR>/20261102/pr/7/
// Для main додатково оновлюються <DEPLOY_DIR>/sosna-latest.{docx,pdf}.
//
// Тип збірки (BUILD_TYPE):
//   dev     - DOCX/PDF із зауваженнями рецензента як примітками Word -> sosna-<N>, sosna-latest;
//   release - чистова версія без приміток -> sosna-release-<N>, sosna-release-latest.
// Автоматичний запуск (push, webhook, опитування SCM, індексація гілок) завжди збирає dev.
// Ручний запуск (Build with Parameters) збирає тип, вибраний у параметрі BUILD_TYPE.
// Версія документа (DOC_VERSION) - короткий SHA коміту; потрапляє у властивості DOCX,
// а в dev-збірці ще й у колонтитул титульного аркуша.
pipeline {
  agent any

  parameters {
    choice(name: 'BUILD_TYPE', choices: ['dev', 'release'],
           description: 'Тип збірки для ручного запуску. Автоматичні запуски з Git завжди dev.')
  }

  options {
    timeout(time: 30, unit: 'MINUTES')
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '10'))
  }

  environment {
    DEPLOY_HOST = 'deploy@ukraine.wg.ukr.lab'
    DEPLOY_DIR  = '/opt/compose-services/proxy/data/www/html'
    UV_BIN      = 'uv'
  }

  stages {
    stage('Resolve build type') {
      steps {
        script {
          // UserIdCause є лише тоді, коли збірку запустив користувач у Jenkins UI
          def manual = !currentBuild.getBuildCauses('hudson.model.Cause$UserIdCause').isEmpty()
          def requested = params.BUILD_TYPE ?: 'dev'   // перший запуск гілки: параметрів ще немає
          env.EFFECTIVE_BUILD_TYPE = manual ? requested : 'dev'
          def causes = currentBuild.getBuildCauses().collect { it.shortDescription }.join('; ')
          echo "Запуск: ${manual ? 'вручну' : 'автоматично'} (${causes})"
          echo "Тип збірки: ${env.EFFECTIVE_BUILD_TYPE}" +
               (manual ? '' : " (автоматичний запуск, параметр BUILD_TYPE=${requested} проігноровано)")
          // build.py бере версію документа зі змінної DOC_VERSION
          env.DOC_VERSION = env.GIT_COMMIT ? env.GIT_COMMIT.take(7) : ''
          echo "Версія документа: ${env.DOC_VERSION ?: '(не визначено, build.py візьме з git)'}"
          currentBuild.description = "${env.EFFECTIVE_BUILD_TYPE} ${env.DOC_VERSION}".trim()
        }
      }
    }

    stage('Build') {
      steps {
        // check: биті посилання, джерела, рисунки й таблиці без посилань;
        // pdf: збирає DOCX і PDF (dev -> build/thesis-dev.*, release -> build/thesis-release.*)
        sh '''
          echo "EFFECTIVE_BUILD_TYPE=$EFFECTIVE_BUILD_TYPE DOC_VERSION=$DOC_VERSION"
          case "$EFFECTIVE_BUILD_TYPE" in
            dev)     FLAG="" ;;
            release) FLAG="--release" ;;
            *)       echo "невідомий EFFECTIVE_BUILD_TYPE=$EFFECTIVE_BUILD_TYPE" >&2; exit 2 ;;
          esac
          $UV_BIN run build.py check
          $UV_BIN run build.py $FLAG pdf
        '''
      }
    }

    stage('Publish') {
      steps {
        sh '''
          DATE=$(date +%Y%m%d)

          # CHANGE_ID задається Jenkins лише для pull/merge request
          if [ -n "$CHANGE_ID" ]; then
            SUBDIR="$DATE/pr/$CHANGE_ID"
          elif [ "$BRANCH_NAME" = "main" ]; then
            SUBDIR="$DATE"
          else
            # feature/x -> feature-x; лише безпечні символи в імені папки
            SAFE=$(printf '%s' "$BRANCH_NAME" | tr -c 'A-Za-z0-9._-' '-')
            SUBDIR="$DATE/$SAFE"
          fi

          # dev і release мають різні імена, щоб release не перезаписував dev і навпаки
          if [ "$EFFECTIVE_BUILD_TYPE" = "release" ]; then
            SRC=build/thesis-release; DST=sosna-release
          else
            SRC=build/thesis-dev;     DST=sosna-dev
          fi

          rm -rf build/out && mkdir -p "build/out/$SUBDIR"
          # Номер збірки в імені: кілька збірок за день не перезаписують одна одну
          cp "$SRC.docx" "build/out/$SUBDIR/$DST-$BUILD_NUMBER.docx"
          cp "$SRC.pdf"  "build/out/$SUBDIR/$DST-$BUILD_NUMBER.pdf"
          cp "$SRC.docx" "build/out/$SUBDIR/$DST-latest.docx"
          cp "$SRC.pdf"  "build/out/$SUBDIR/$DST-latest.pdf"
          if [ -z "$CHANGE_ID" ] && [ "$BRANCH_NAME" = "main" ]; then
            cp "$SRC.docx" "build/out/$DST-latest.docx"
            cp "$SRC.pdf"  "build/out/$DST-latest.pdf"
          fi
          echo "$SUBDIR" > build/subdir.txt
        '''
        withCredentials([sshUserPrivateKey(credentialsId: 'deploy_github_ssh',
                                           keyFileVariable: 'SSH_KEY')]) {
          // Одинарні лапки: шлях до ключа підставляє shell, а не Groovy.
          // Без --delete: файли інших гілок і дат на сервері не зачіпаються.
          sh '''
            SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new"
            $SSH "$DEPLOY_HOST" "mkdir -p '$DEPLOY_DIR/$(cat build/subdir.txt)'"
            rsync -av -O -e "$SSH" build/out/ "$DEPLOY_HOST:$DEPLOY_DIR/"
          '''
        }
      }
    }
  }

  post {
    success { archiveArtifacts artifacts: 'build/out/**', fingerprint: true }
  }
}
