export class ParallelCoordinates {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.options = {
            width: options.width || 300,
            height: options.height || 250,
            margin: options.margin || { top: 30, right: 10, bottom: 10, left: 10 },
            color: options.color || d3.scaleOrdinal(['#483d8b', '#ff6b6b']),
            maxValue: options.maxValue || 1
        };

        this.data = options.data || [
            {
                className: "metrics-quartiere1",
                axes: [
                    { axis: "Proximity", value: 0.2 },
                    { axis: "Density", value: 0.2 },
                    { axis: "Entropy", value: 0.2 },
                    { axis: "Accessibility", value: 0.2 },
                    { axis: "Closeness", value: 0.2 }
                ]
            },
            {
                className: "metrics-quartiere2",
                axes: [
                    { axis: "Proximity", value: 0.2 },
                    { axis: "Density", value: 0.2 },
                    { axis: "Entropy", value: 0.2 },
                    { axis: "Accessibility", value: 0.2 },
                    { axis: "Closeness", value: 0.2 }
                ]
            }
        ];

        this.initChart();
    }

    initChart() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Container with id '${this.containerId}' not found`);
            return;
        }

        const existingSvg = container.querySelector('svg');
        if (existingSvg) {
            existingSvg.remove();
        }

        const { width, height, margin } = this.options;
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        this.svg = d3.select(`#${this.containerId}`)
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .attr("class", "parallel-coordinates");

        this.g = this.svg.append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        this.dimensions = this.data[0].axes.map(d => d.axis);

        this.y = {};
        this.dimensions.forEach(dim => {
            this.y[dim] = d3.scaleLinear()
                .domain([0, this.options.maxValue])
                .range([innerHeight, 0]);
        });

        this.x = d3.scalePoint()
            .domain(this.dimensions)
            .range([0, innerWidth])
            .padding(0.1);

        this.drawLines();

        this.drawAxes(innerHeight);

        this.addInteractivity();
    }

    drawLines() {
        const line = d3.line()
            .defined(d => !isNaN(d[1]))
            .x(d => this.x(d[0]))
            .y(d => this.y[d[0]](d[1]));

        this.background = this.g.append("g")
            .attr("class", "background")
            .selectAll("path")
            .data(this.data)
            .enter()
            .append("path")
            .attr("class", (d, i) => `line line-${i}`)
            .attr("d", d => {
                const points = d.axes.map(axis => [axis.axis, axis.value]);
                return line(points);
            })
            .style("fill", "none")
            .style("stroke", (d, i) => {
                if (typeof this.options.color === "function") {
                    return this.options.color(i);
                } else if (Array.isArray(this.options.color)) {
                    return this.options.color[i % this.options.color.length];
                } else {
                    return this.options.color;
                }
            })
            .style("stroke-width", "3px")
            .style("opacity", 0.7);

        this.foreground = this.g.append("g")
            .attr("class", "foreground")
            .selectAll("path")
            .data(this.data)
            .enter()
            .append("path")
            .attr("class", (d, i) => `line line-${i}`)
            .attr("d", d => {
                const points = d.axes.map(axis => [axis.axis, axis.value]);
                return line(points);
            })
            .style("fill", "none")
            .style("stroke", (d, i) => {
                if (typeof this.options.color === "function") {
                    return this.options.color(i);
                } else if (Array.isArray(this.options.color)) {
                    return this.options.color[i % this.options.color.length];
                } else {
                    return this.options.color;
                }
            })
            .style("stroke-width", "2px")
            .style("opacity", 0);
    }

    drawAxes(innerHeight) {
        const axis = this.g.selectAll(".dimension")
            .data(this.dimensions)
            .enter()
            .append("g")
            .attr("class", "dimension")
            .attr("transform", d => `translate(${this.x(d)},0)`);

        axis.append("line")
            .attr("y1", 0)
            .attr("y2", innerHeight)
            .style("stroke", "#ddd")
            .style("stroke-width", "1px");

        axis.append("text")
            .attr("class", "axis-label")
            .style("text-anchor", "middle")
            .style("font-size", "12px")
            .style("font-weight", "500")
            .style("fill", "#483d8b")
            .attr("y", -9)
            .text(d => d);

        axis.each((dimension, i, nodes) => {
            const axisGroup = d3.select(nodes[i]);
            const scale = this.y[dimension];
            
            const ticks = [0, 0.25, 0.5, 0.75, 1];
            
            axisGroup.selectAll(".tick")
                .data(ticks)
                .enter()
                .append("g")
                .attr("class", "tick")
                .attr("transform", d => `translate(0,${scale(d)})`)
                .each(function(d) {
                    const tick = d3.select(this);
                    tick.append("line")
                        .attr("x1", -4)
                        .attr("x2", 4)
                        .style("stroke", "#999")
                        .style("stroke-width", "1px");
                    
                    if (i === 0 || i === nodes.length - 1) {
                        tick.append("text")
                            .attr("x", i === 0 ? -8 : 8)
                            .attr("dy", "0.32em")
                            .style("text-anchor", i === 0 ? "end" : "start")
                            .style("font-size", "10px")
                            .style("fill", "#666")
                            .text(d.toFixed(2));
                    }
                });
        });
    }

    addInteractivity() {
        this.foreground
            .on("mouseover", (event, d) => {
                this.background.style("opacity", 0.2);
                this.foreground.style("opacity", 0);
                
                d3.select(event.currentTarget)
                    .style("opacity", 1)
                    .style("stroke-width", "4px");
                
                const datasetIndex = this.data.indexOf(d);
                const areaName = datasetIndex === 0 ? "1° area" : "2° area";
                this.showTooltip(event, d, areaName);
            })
            .on("mouseout", () => {
                this.background.style("opacity", 0.7);
                this.foreground.style("opacity", 0);
                
                this.hideTooltip();
            });

        this.background
            .on("mouseover", (event, d) => {
                this.background.style("opacity", 0.2);
                
                d3.select(event.currentTarget)
                    .style("opacity", 1)
                    .style("stroke-width", "4px");
                
                const datasetIndex = this.data.indexOf(d);
                const areaName = datasetIndex === 0 ? "1° area" : "2° area";
                this.showTooltip(event, d, areaName);
            })
            .on("mouseout", () => {
                this.background
                    .style("opacity", 0.7)
                    .style("stroke-width", "3px");
                
                this.hideTooltip();
            });
    }

    showTooltip(event, data, areaName) {
        this.svg.selectAll(".pc-tooltip").remove();

        const tooltip = this.svg.append("g")
            .attr("class", "pc-tooltip")
            .style("pointer-events", "none");

        const bg = tooltip.append("rect")
            .attr("fill", "white")
            .attr("stroke", "#999")
            .attr("stroke-width", 1)
            .attr("rx", 4)
            .attr("ry", 4);

        const textGroup = tooltip.append("text")
            .attr("class", "tooltip-text")
            .style("font-size", "11px")
            .style("fill", "#333");

        textGroup.append("tspan")
            .attr("x", 0)
            .attr("dy", "1.2em")
            .style("font-weight", "bold")
            .text(areaName);

        data.axes.forEach((axis, i) => {
            textGroup.append("tspan")
                .attr("x", 0)
                .attr("dy", "1.2em")
                .text(`${axis.axis}: ${(axis.value * 100).toFixed(0)}%`);
        });

        const bbox = textGroup.node().getBBox();
        bg.attr("x", bbox.x - 8)
            .attr("y", bbox.y - 4)
            .attr("width", bbox.width + 16)
            .attr("height", bbox.height + 8);

        const [mouseX, mouseY] = d3.pointer(event);
        tooltip.attr("transform", `translate(${mouseX + 10},${mouseY - 10})`);
    }

    hideTooltip() {
        this.svg.selectAll(".pc-tooltip").remove();
    }

    updateData(newData) {
        this.data = newData;
        if (this.svg) {
            this.svg.remove();
        }
        this.initChart();
    }
}

