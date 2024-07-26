# LeGEND
This is the repository for our paper "LeGEND: A Top-Down Approach to Scenario Generation of Autonomous Driving Systems Assisted by Large Language Models"

## Requirements
* Apollo 7.0
* LGSVL 2021.3
* GPT4 API

## Run
Step 1: Clone this project <br />
Step 2: Define your scenario config in ```configs/config.yaml``` <br />
Step 3: ```python3 main.py```

## Project Structure
```
.
├── configs
│   ├── config.yaml
│   ├── curve_road
│   │   ├── basic.json
│   │   ├── basic.txt
│   │   └── road.json
│   └── straight_road
│       ├── basic.json
│       ├── basic.txt
│       ├── road_500m.json
│       └── road.json
├── data
│   └── accident_reports
├── legend
│   ├── core
│   │   ├── algorithm.py
│   │   ├── chromosome.py
│   │   ├── converter.py
│   │   ├── extractor.py
│   │   ├── scenario_model.py
│   │   ├── simulation.py
│   │   ├── statement.py
│   │   └── testcase.py
│   └── utils
│       ├── fnds.py
│       ├── llm_util.py
│       ├── replay.py
│       └── sim_util.py
├── lgsvl
├── main.py
├── README.md
└── requirements.txt




