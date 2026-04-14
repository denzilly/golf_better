We are going to design a golf bet tracker for a two person golf betting game.

Each player selects 3 golfers.
The game is played on large golf tournaments, and the end result is based on the results of the players in the tournament.

A stake is decided in euros--usually 1 or 2 euros.

stake pays out in a number of ways:
- stroke to par. If a golfer scores two under par, the result is 2 * stake
- birdie/eagle bonus. for consecutive birdies or eagles, an additional bonus is given. The second birdie in a row gives 1 bonus point, the second gives 3 bonus points, the third gives 7. If one of the consecutives is an eagle, it's worth double points. result is points * stake

- if a player makes the top 10, a bonus is awarded. first place receives 100 euro extra, second 90, etc. If it is a T2 with 3 players, we take the average of places 2-3-4

- if a plyer doesnt make the cut, there is a 25 euro penalty.



- I want you to design a web interface that makes it easy to track golf bets like these, and also show intermittent scores as the tournament is ongoing

- I want the ability to add a new tournament, and add players to that tournament
- I want to consider how we can scrape the scores of these tournaments automatically