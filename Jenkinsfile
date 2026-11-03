// Multibranch Pipeline: Jenkins збирає кожну змінену гілку і кожен pull request.
// Результати публікуються на сервер у папку за датою збірки:
//   main          -> <DEPLOY_DIR>/20261102/
//   гілка feature -> <DEPLOY_DIR>/20261102/feature/
//   PR №7         -> <DEPLOY_DIR>/20261102/pr/7/
// Для main додатково оновлюються <DEPLOY_DIR>/thesis-latest.{docx,pdf}.
pipeline {
  agent any

  options {
    timeout(time: 30, unit: 'MINUTES')
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20', artifactNumToKeepStr: '10'))
  }

  environment {
    DEPLOY_HOST = 'deploy@ukraine.wg.ukr.lab'
    DEPLOY_DIR  = '/opt/compose-services/proxy/app-data/config/www/html'
    UV_BIN      = 'uv'
  }

  stages {
    stage('Build') {
      steps {
        // check: биті посилання, джерела, рисунки й таблиці без посилань;
        // pdf: збирає DOCX і PDF
        sh '''
          $UV_BIN run build.py check
          $UV_BIN run build.py pdf
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

          rm -rf build/out && mkdir -p "build/out/$SUBDIR"
          # Номер збірки в імені: кілька збірок за день не перезаписують одна одну
          cp build/thesis.docx "build/out/$SUBDIR/thesis-$BUILD_NUMBER.docx"
          cp build/thesis.pdf  "build/out/$SUBDIR/thesis-$BUILD_NUMBER.pdf"
          cp build/thesis.docx "build/out/$SUBDIR/thesis-latest.docx"
          cp build/thesis.pdf  "build/out/$SUBDIR/thesis-latest.pdf"
          if [ -z "$CHANGE_ID" ] && [ "$BRANCH_NAME" = "main" ]; then
            cp build/thesis.docx build/out/thesis-latest.docx
            cp build/thesis.pdf  build/out/thesis-latest.pdf
          fi
          echo "$SUBDIR" > build/subdir.txt
        '''
        withCredentials([sshUserPrivateKey(credentialsId: '8d52afd5-38dd-40c6-ab9e-5dccb7e72231',
                                           keyFileVariable: 'SSH_KEY')]) {
          // Одинарні лапки: шлях до ключа підставляє shell, а не Groovy.
          // Без --delete: файли інших гілок і дат на сервері не зачіпаються.
          sh '''
            SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new"
            $SSH "$DEPLOY_HOST" "mkdir -p '$DEPLOY_DIR/$(cat build/subdir.txt)'"
            rsync -av -e "$SSH" build/out/ "$DEPLOY_HOST:$DEPLOY_DIR/"
          '''
        }
      }
    }
  }

  post {
    success { archiveArtifacts artifacts: 'build/out/**', fingerprint: true }
  }
}
