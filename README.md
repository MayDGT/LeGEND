# LeGEND
This is the repository for our paper "LeGEND: A Top-Down Approach to Scenario Generation of Autonomous Driving Systems Assisted by Large Language Models"

## Approach Overview
![approach overview](images/website_overview.png)

The workflow of our approach is depicted in the above figure, which consists of three phases. The first two phases are in charge of the transformation from natural language that documents functional scenarios to logical scenarios in formal DSL:
* In Phase 1, LLM<sub>1</sub> extracts the useful information in an accident report and records them into an interactive pattern sequence (IPS);
* In Phase 2, taking an IPS as input, LLM<sub>2</sub> translates it into a logical scenario represented in Domain Specific Language (DSL). <br />

In the last phase, LeGEND employs a search-based technique to search for critical concrete scenarios, which is similar to existing studies.


## Dependencies
* Ubuntu 22.04 LTS
* Apollo 7.0
* LGSVL 2021.3
* GPT-4

## Usage
To reproduce the experimental results, users should follow the steps below:
### Preparation
* Install Baidu Apollo following [Apollo Installation](https://github.com/ApolloAuto/apollo?tab=readme-ov-file#installation)
* Install LGSVL simulator following [LGSVL Installation](https://github.com/YuqiHuai/SORA-SVL)
* Clone this project and install the required packages: <br />
  ```pip install -r requirements.txt```
* Set your ChatGPT API key and other configurations in ```configs/config.yaml```
### Run
* Start LGSVL simulator
* Start Apollo inside the apollo container: <br />
  ``` bash scripts/bootstrap.sh ``` <br />
  ``` bash scripts/bridge ```
* Run LeGEND: <br />
  ```python3 main.py```
* The results will be stored in ``` data/results ```, and the system log will be stored in ``` data/logs ```

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




