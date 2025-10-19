#!/bin/bash

export PGPASSWORD="${PGPASSWORD:-$POSTGRES_PASSWORD}"
psql=( psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --no-password )

for db in local_db ccontrol chanfix dronescan; do
  "${psql[@]}" --dbname postgres --set db="$db" <<-'EOSQL'
				CREATE DATABASE :"db";
			EOSQL
  echo
done

#echo "$0: Setting up cservice db"
#for sql_file in cservice.sql languages.sql language_table.sql cservice.help.sql cservice.web.sql cservice.config.sql cservice.addme.sql greeting.sql; do
#  ${psql[@]} --dbname cservice < /gnuworld/doc/${sql_file}
#done

echo "$0: Setting up ccontrol db"
for sql_file in ccontrol.sql ccontrol.help.sql ccontrol.addme.sql ccontrol.commands.sql; do
  ${psql[@]} --dbname ccontrol < /gnuworld/doc/${sql_file}
done

echo "$0: Setting up chanfix db"
for sql_file in chanfix.sql chanfix.languages.sql chanfix.language.english.sql chanfix.help.sql chanfix.addme.sql; do
  ${psql[@]} --dbname chanfix < /gnuworld/mod.openchanfix/doc/${sql_file}
done

echo "$0: Setting up dronescan db"
${psql[@]} --dbname dronescan < /gnuworld/doc/dronescan.sql

echo "$0: Setting up local db"
${psql[@]} --dbname local_db < /gnuworld/doc/cservice.web.sql

echo "$0: Loading themes into local_db..."
for theme in $(find /cservice-web/docs/gnuworld/themes/data -name "*.sql"); do
  cat $theme | ${psql[@]} --dbname local_db
done

# Create initialization completion marker
echo "$0: Creating initialization completion marker..."
${psql[@]} --dbname cservice <<-'EOSQL'
	CREATE TABLE IF NOT EXISTS init_completed (completed_at TIMESTAMP DEFAULT NOW());
	INSERT INTO init_completed VALUES (NOW());
EOSQL
echo "$0: Database initialization complete!"
