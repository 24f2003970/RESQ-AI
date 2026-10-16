# Mission Clock Model

The mission operational clock is a separate SQLite-backed clock for each `(scenario_id, epoch)`. Flood simulation advances in its existing five-minute ticks; mission time advances only through explicit 1–30 second commands. The clocks are not synchronized and no wall-clock elapsed time is inferred.

Each advance includes the expected mission-clock version and flood `state_version`. The backend rejects stale versions, paused clocks, and inactive epochs. Movement is deterministic: available seconds traverse route segments at the route's synthetic segment speed, defaulting to 6 m/s only when a speed is absent. Distance, segment index, 3D position, remaining distance, synthetic elapsed travel time, ETA, and arrival are persisted together.

The frontend may interpolate visually between backend snapshots for smooth display. It cannot advance simulation state or declare arrival. Restart reloads the persisted clock and route progress. Clock and mission events provide the operational timeline. Synthetic travel speeds are educational assumptions, not emergency response estimates.
