import json
from pathlib import Path
import re


def create_insect_name_map():
    """
    解析您提供的1-indexed昆虫名称列表，并创建一个从'1'到'102'的名称映射。
    """
    insect_list_text = """
    1  rice leaf roller
    2  rice leaf caterpillar
    3  paddy stem maggot
    4  asiatic rice borer
    5  yellow rice borer
    6  rice gall midge
    7  Rice Stemfly
    8  brown plant hopper
    9  white backed plant hopper
    10 small brown plant hopper
    11 rice water weevil
    12 rice leafhopper
    13 grain spreader thrips
    14 rice shell pest
    15 grub
    16 mole cricket
    17 wireworm
    18 white margined moth
    19 black cutworm
    20 large cutworm
    21 yellow cutworm
    22 red spider
    23 corn borer
    24 army worm
    25 aphids
    26 Potosiabre vitarsis
    27 peach borer
    28 english grain aphid
    29 green bug
    30 bird cherry-oataphid
    31 wheat blossom midge
    32 penthaleus major
    33 longlegged spider mite
    34 wheat phloeothrips
    35 wheat sawfly
    36 cerodonta denticornis
    37 beet fly
    38 flea beetle
    39 cabbage army worm
    40 beet army worm
    41 Beet spot flies
    42 meadow moth
    43 beet weevil
    44 sericaorient alismots chulsky
    45 alfalfa weevil
    46 flax budworm
    47 alfalfa plant bug
    48 tarnished plant bug
    49 Locustoidea
    50 lytta polita
    51 legume blister beetle
    52 blister beetle
    53 therioaphis maculata Buckton
    54 odontothrips loti
    55 Thrips
    56 alfalfa seed chalcid
    57 Pieris canidia
    58 Apolygus lucorum
    59 Limacodidae
    60 Viteus vitifoliae
    61 Colomerus vitis
    62 Brevipoalpus lewisi McGregor
    63 oides decempunctata
    64 Polyphagotars onemus latus
    65 Pseudococcus comstocki Kuwana
    66 parathrene regalis
    67 Ampelophaga
    68 Lycorma delicatula
    69  Xylotrechus
    70  Cicadella viridis
    71  Miridae
    72  Trialeurodes vaporariorum
    73  Erythroneura apicalis
    74  Papilio xuthus
    75  Panonchus citri McGregor
    76  Phyllocoptes oleiverus ashmead
    77  Icerya purchasi Maskell
    78  Unaspis yanonensis
    79  Ceroplastes rubens
    80  Chrysomphalus aonidum
    81  Parlatoria zizyphus Lucus
    82  Nipaecoccus vastalor
    83  Aleurocanthus spiniferus
    84  Tetradacus c Bactrocera minax
    85  Dacus dorsalis(Hendel)
    86  Bactrocera tsuneonis
    87  Prodenia litura
    88  Adristyrannus
    89  Phyllocnistis citrella Stainton
    90  Toxoptera citricidus
    91  Toxoptera aurantii
    92  Aphis citricola Vander Goot
    93  Scirtothrips dorsalis Hood
    94  Dasineura sp
    95  Lawana imitata Melichar
    96  Salurnis marginella Guerr
    97  Deporaus marginatus Pascoe
    98  Chlumetia transversa
    99  Mango flat beak leafhopper
    100 Rhytidodera bowrinii white
    101 Sternochetus frigidus
    102 Cicadellidae
    """

    name_map = {}
    lines = insect_list_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^\s*(\d+)\s+(.*)$', line)
        if match:
            idx = match.group(1)
            name = match.group(2).strip()
            name_map[idx] = name
    print(f"✅ 成功解析 {len(name_map)} 个昆虫名称。")
    return name_map


def generate_knowledge_base(input_json_path: Path, output_dir: Path):
    """
    整合 idx_to_label.json 和昆虫名称，生成最终的知识库文件。
    """
    output_path = output_dir / "knowledge_base.json"

    if not input_json_path.exists():
        print(f"❌ 错误: 输入文件 '{input_json_path}' 未找到。请检查路径是否正确。")
        return

    print(f"📄 正在读取模型原始标签映射: {input_json_path}")
    with open(input_json_path, 'r', encoding='utf-8') as f:
        idx_to_label = json.load(f)

    insect_name_map = create_insect_name_map()

    knowledge_base = {}
    print("\n🔄 正在生成知识库，并修正索引...")

    for str_idx, original_label in idx_to_label.items():
        entry = {
            "original_label": original_label,
            "dataset": "",
            "readable_name": ""
        }
        if original_label.startswith("ip102_"):
            entry["dataset"] = "IP102 (昆虫)"
            try:
                # 核心修正逻辑：
                # 1. 从 "ip102_0" 中提取数字 0
                insect_id_from_label = int(original_label.replace("ip102_", ""))
                # 2. 将 0-indexed 的标签ID (+1) 转换为 1-indexed 的列表key '1'
                map_key = str(insect_id_from_label + 1)
                # 3. 使用修正后的key从昆虫名录中查找名称
                entry["readable_name"] = insect_name_map.get(map_key, f"名称未在列表中找到 (ID: {map_key})")
            except (ValueError, TypeError):
                entry["readable_name"] = f"无效的昆虫标签 ({original_label})"
        elif original_label.startswith("pp_"):
            disease_name = original_label.replace("pp_", "").replace("_", " ").title()
            entry["dataset"] = "Plant Pathology (植物病害)"
            entry["readable_name"] = disease_name
        else:
            entry["dataset"] = "未知"
            entry["readable_name"] = original_label

        knowledge_base[str_idx] = entry

    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=4)

    print(f"\n🎉 成功！知识库文件已修正并保存至: {output_path}")


if __name__ == "__main__":
    # 使用您文件系统中的绝对路径
    base_project_dir = Path(r"F:\machinelearning\shizhan\crop_pest_disease_classifier")

    # 输入文件路径
    input_file_path = base_project_dir / "datasets" / "processed" / "idx_to_label_multilabel.json"

    # 输出文件夹路径
    output_directory = base_project_dir / "trained_models"

    print("--- 开始生成病虫害知识库 (最终确认版) ---")
    generate_knowledge_base(input_json_path=input_file_path, output_dir=output_directory)
    print("-" * 40)