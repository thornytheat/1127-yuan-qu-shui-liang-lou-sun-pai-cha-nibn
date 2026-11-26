function drawProjectChart(target, points) {
    const feed = named('ol',undefined,'audit-stream');
    const maxValue = Math.max(1,...points.map(i=>Math.abs(i.value)));
    for (const {label,value} of points) {
        const row = named('li');
        const magnitude = Math.min(24,Math.max(1,Math.round(Math.abs(value)/maxValue*24)));
        row.append(named('code',label),named('span','▰'.repeat(magnitude),'signal-glyph'),named('output',value));
        feed.append(row);
    }
    target.append(feed);
}
