export function draw(target, data, {node, mark, choose}) {
  const map = node('div');
  const scale = node('div','','hot-row heat-label');
  scale.append(node('span','层位'));
  Array.from({length:8},(_,i)=>scale.append(node('span',String(i+1))));
  map.append(scale);
  const regions = Object.keys(data.cohorts.current_by_region).filter(region=>data.decisions.some(row=>row.region===region && row.estimate!==null));
  for (const zone of regions) {
    const row = node('div','','hot-row');
    row.append(node('span',zone));
    for (let level=1;level<=8;level+=1) {
      const highest=data.decisions.filter(item=>item.region===zone && item.raw.level===level && item.estimate!==null)
        .sort((left,right)=>right.estimate-left.estimate)[0];
      if (!highest) { row.append(node('i')); continue; }
      const item=node('button',mark(highest.estimate),'viz-button');
      item.dataset.key=highest.key;
      item.type='button';
      item.setAttribute('aria-label',`${zone}第 ${level} 层预测含水 ${mark(highest.estimate)}%`);
      item.style.setProperty('--heat',`${91-Math.min(37,Math.max(0,highest.estimate-7)*5)}%`);
      item.onclick=()=>choose(highest.key);
      row.append(item);
    }
    map.append(row);
  }
  target.replaceChildren(map,node('p',`按层位显示预测含水率 %。留窗误差带 ±${mark(data.replay.radius)} 个百分点。`,'chart-caption'));
}
