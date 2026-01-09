export { matchers } from './matchers.js';

export const nodes = [
	() => import('./nodes/0'),
	() => import('./nodes/1'),
	() => import('./nodes/2'),
	() => import('./nodes/3'),
	() => import('./nodes/4'),
	() => import('./nodes/5'),
	() => import('./nodes/6'),
	() => import('./nodes/7'),
	() => import('./nodes/8'),
	() => import('./nodes/9'),
	() => import('./nodes/10'),
	() => import('./nodes/11'),
	() => import('./nodes/12'),
	() => import('./nodes/13'),
	() => import('./nodes/14'),
	() => import('./nodes/15'),
	() => import('./nodes/16'),
	() => import('./nodes/17'),
	() => import('./nodes/18'),
	() => import('./nodes/19'),
	() => import('./nodes/20')
];

export const server_loads = [];

export const dictionary = {
		"/": [4],
		"/admin": [5,[2]],
		"/admin/campaigns": [6,[2]],
		"/admin/certificates": [7,[2]],
		"/admin/events": [8,[2]],
		"/admin/events/new": [10,[2]],
		"/admin/events/[id]": [9,[2]],
		"/admin/providers": [11,[2]],
		"/admin/templates": [12,[2]],
		"/events/[slug]": [13],
		"/login": [14],
		"/portal": [15,[3]],
		"/portal/certificates": [16,[3]],
		"/portal/login": [17,[3]],
		"/portal/prizes": [18,[3]],
		"/portal/verify": [19,[3]],
		"/verify": [20]
	};

export const hooks = {
	handleError: (({ error }) => { console.error(error) }),
	
	reroute: (() => {}),
	transport: {}
};

export const decoders = Object.fromEntries(Object.entries(hooks.transport).map(([k, v]) => [k, v.decode]));
export const encoders = Object.fromEntries(Object.entries(hooks.transport).map(([k, v]) => [k, v.encode]));

export const hash = false;

export const decode = (type, value) => decoders[type](value);

export { default as root } from '../root.js';