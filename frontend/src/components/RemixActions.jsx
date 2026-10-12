import React from 'react';
import RemixWorkspace from './RemixWorkspace';

export default function RemixActions(props) {
  return <RemixWorkspace key={`${props.sourceKind}:${props.fileName}`} {...props} />;
}
