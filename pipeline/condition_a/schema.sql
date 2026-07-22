CREATE TABLE title (id INT PRIMARY KEY, title TEXT, production_year INT, kind_id INT);
CREATE TABLE cast_info (id INT PRIMARY KEY, movie_id INT, person_id INT, role_id INT);
