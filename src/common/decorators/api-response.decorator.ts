import { applyDecorators, Type } from '@nestjs/common';
import { ApiResponse, ApiResponseOptions, getSchemaPath } from '@nestjs/swagger';

export function ApiResponseDecorator<TModel extends Type<any>>(model: TModel, options: ApiResponseOptions = {}) {
  return applyDecorators(
    ApiResponse({
      ...options,
      schema: {
        allOf: [
          { $ref: getSchemaPath(model) },
        ],
      },
    }),
  );
}
