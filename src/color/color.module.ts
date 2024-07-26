import { Module } from '@nestjs/common';
import { ColorService } from './color.service';

@Module({
  providers: [ColorService],
  exports: [ColorService],
})
export class ColorModule {}
