# Catalog Items Project (With A Twist)

I decided to challenge myself a little more than what the project rubric called for. I created a web application designed to keep track of sports leagues. On the public side, you can view leagues, teams, upcoming games and scores. If you log in you can create leagues and become the administrator for that league. With these privileges, an administrator can create/read/update/delete (CRUD) leagues, teams, games and final scores.

## Public JSON Endpoints

* ```/leagues/json``` - Contains information about all leagues including teams and games
* ```/leagues/<league_id>/json``` - Contains information about a specific league including teams and games
* ```/leagues/<league_id>/<team_id>/json``` - Contains information about a team including games

## Requirements
* [Python 3](http://www.python.org/)
* [Vagrant](https://www.vagrantup.com/downloads.html)
* [VirtualBox](https://www.virtualbox.org/wiki/Downloads)
* [Udacity Virtual Machine](https://github.com/udacity/fullstack-nanodegree-vm)
* [python-slugify](https://github.com/un33k/python-slugify) ** Must be installed in the VM **

## Project Setup
1. Install Vagrant and VirtualBox
2. Clone the Udacity Vagrant VM repository
3. Clone this repository and copy its contents to the `/vagrant/catalog` directory in the Udacity Vagrant Virtual Machine
4. Open terminal and change the directory to the folder containing the Virtual Machine
5. Start up the virtual machine
    ```
    vagrant up
    ```
6. Log in to the virtual machine
    ```
    vagrant ssh
    ```
7. Install python-slugify
    ```
    sudo pip3 install python-slugify
    ```
8. Change to project directory
    ```
    cd /vagrant/catalog
    ```
9. Run the database seeder
    ```
    python3 database_seed.py
    ```
10. Run the project
    ```
    python3 views.py
    ```

## Credits
* [Udacity Fullstack Nanodegree](https://classroom.udacity.com/nanodegrees/nd004)
